import os
import sys
import time
# 使用相对路径添加项目根目录到 Python 搜索路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

import json
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
import black

import os
import json
import networkx as nx
import logging
from typing import List, Dict

# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

GRAPH_DIR = "/home/shixianjie/codegraph/codegraph/data_process/repograph"
# 设置可见的 CUDA 设备为 2 和 3
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
# 设置 HuggingFace 镜像站点
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"
os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"



def read_jsonl(file_path):
    """
    读取 JSONL 文件并将其解析为 Python 对象列表。
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                data.append(json.loads(line.strip()))
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e} in line: {line.strip()}")
    return data


def build_code_map(repo_path, reponame):
    """
    针对当前处理的数据，动态生成一个临时的 namespace -> code 的映射。

    参数:
    - repo_path (str): 仓库路径
    - reponame (str): 当前项目的名称

    返回:
    - code_map (dict): 当前项目的 namespace -> code 映射
    """
    code_map = {}
    files = [
        os.path.join(repo_path, f"{reponame}_functions.json"),
        os.path.join(repo_path, f"{reponame}_methods.json"),
        os.path.join(repo_path, f"{reponame}_classes.json")
    ]
    # 遍历文件，动态生成 code_map
    for file in files:
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        item = json.loads(line.strip())
                        namespace = item.get("name", "")
                        code = item.get("code", "")
                        
                        # 添加到 code_map
                        if namespace and namespace not in code_map:
                            code_map[namespace] = {
                                "code": code,
                                "path": item.get("path", "")
                            }
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON in file {file}: {e}")
    
    return code_map

def extract_related_code(dependencies, code_map):
    """
    从依赖中提取相关代码。

    参数:
    - dependencies (dict): 包含 child_requirement, context_requirement, similarity_requirement 的依赖关系
    - code_map (dict): 当前项目的 namespace -> code 映射

    返回:
    - related_code (dict): 包含各类依赖相关代码的字典
    """
    related_code = {key: [] for key in dependencies}
    
    for category, namespaces in dependencies.items():
        for ns in namespaces:
            if ns in code_map:
                related_code[category].append({
                    "namespace": ns,
                    "code": code_map[ns]["code"],
                    # "path": code_map[ns]["path"]
                })
    
    return related_code




def load_graph(input_path: str) -> nx.Graph:
    """
    Load a graph from a JSON file.
    """
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
        graph = nx.node_link_graph(data)
        print(f"Graph successfully loaded: {input_path}")
        return graph
    except FileNotFoundError:
        # print(f"Graph file not found: {input_path}")
        return None
    except Exception as e:
        # print(f"Error loading graph: {e}")
        return None


def get_caller_nodes_for_namespace(namespace: str) -> Dict:
    """
    Retrieve the caller nodes related to a given namespace.
    """
    reponame = namespace.split('.')[0]
    graph_path = os.path.join(GRAPH_DIR,f"{reponame}", f"{reponame}.json")
    if not os.path.exists(graph_path):
        raise ValueError(f"Graph database file {graph_path} does not exist")
    
    graph = load_graph(graph_path)  
    caller_nodes = []
    container_nodes = []

    for u, v, data in graph.edges(data=True):
        if data.get("relationship") == "CALLS" and data.get('target_namespace') == namespace:
            caller_nodes.append(u)
        if data.get("relationship") == "CONTAINS" and data.get('target_namespace') == namespace:
            container_nodes.append(u)
    
    related_code = {
        "namespace": namespace,
        "caller_nodes": [],
        "container_nodes": []
    }
    
    for node in caller_nodes:
        node_data = graph.nodes[node]
        related_code["caller_nodes"].append(format_node_data(node_data))
    
    for node in container_nodes:
        node_data = graph.nodes[node]
        related_code["container_nodes"].append(format_node_data(node_data))
    
    print(f"Found {len(caller_nodes)} CALLS relationships and {len(container_nodes)} CONTAINS relationships for namespace {namespace}")
    return related_code


def format_node_data(node_data: Dict) -> Dict:
    """
    Format and return the node data as a JSON-compatible dictionary.
    """
    return {
        "namespace": node_data.get('namespace', ''),
        "name": node_data.get('name', ''),
        "path": node_data.get('path', ''),
        "type": node_data.get('type', '').split('_')[0],
        "code": node_data.get('code', '')
    }


@tool
def related_code_tool(namespace: str) -> str:
    """
    Tool to retrieve related code for a given namespace based on its dependencies and relationships.
    
    :param namespace: The namespace for which related code is retrieved.
    :return: A JSON string of related code organized by dependency type.
    """
    try:
        related_code = get_caller_nodes_for_namespace(namespace)
        return json.dumps(related_code, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=4, ensure_ascii=False)

    
@tool
def duckduckgo_search_tool(query: str) -> str: 
    """
    使用 DuckDuckGo 进行网络搜索并总结结果
    :param query: 搜索请求
    :return: 搜索的总结结果
    """
    search = DuckDuckGoSearchRun()
    os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0,api_key="sk-yumU7r4GpBMVnTWa1289B0Ac660d406e8370205664863a6a",)  
    
    try:
        # 使用 DuckDuckGo 进行搜索
        search_results = search.invoke(query)
        
        # 如果没有搜索果，返回默认信息
        if not search_results:
            return "No results found."
        
        # 创建用于 LLM 总结的 prompt
        summary_prompt = f"""
        Summarize the following search results into a concise and informative summary:
        
        {search_results}
        
        The summary should capture the most relevant information related to the query: '{query}'.
        """
        
        # 使用 GPT-4 对搜索结果进行总结
        summary_result = llm.invoke(summary_prompt)
        
        return summary_result.content if summary_result else "Failed to summarize the results."
    
    except Exception as e:
        return f"Error searching and summarizing: {str(e)}"


@tool
def code_search_tool(namespace: str) -> str:
    """
    Tool to retrieve related code for a given namespace based on its dependencies.
    This tool uses pre-defined paths for dependency files and repository.
    
    :param namespace: The target namespace for which to retrieve related code.
    :return: A JSON string of related code organized by dependency type.
    """
    try:
        # 固定文件路径
        repo_path = "/home/shixianjie/codegraph/codegraph/Agent/repocode"
        filtered_file = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/Requirementsgraph/codev2/filtered.jsonl"
        meta_file = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/promptelements/LM_prompt_elements_merged.jsonl"

        # Step 1: 读取依赖数据和元数据
        dependencies_data = read_jsonl(filtered_file)
        meta_data = {item["namespace"]: item for item in read_jsonl(meta_file)}

        # Step 2: 查找目标命名空间的依赖信息
        dep_entry = next((dep for dep in dependencies_data if dep.get("namespace") == namespace), None)
        if not dep_entry:
            return json.dumps({"error": f"Namespace `{namespace}` not found in dependencies."}, indent=2)

        dependencies = dep_entry.get("dependency", {})
        if namespace not in meta_data:
            return json.dumps({"error": f"Namespace `{namespace}` not found in metadata."}, indent=2)

        data = meta_data[namespace]
        project_path = data.get("project_path", "")
        if not project_path:
            return json.dumps({"error": f"Project path not found for namespace `{namespace}`."}, indent=2)

        # Step 3: 构建当前项目的 code_map
        reponame = project_path.split("/")[-1]
        code_map = build_code_map(repo_path, reponame)

        # Step 4: 提取相关代码
        related_code = extract_related_code(dependencies, code_map)

        # Step 5: 返回结果
        return json.dumps(related_code, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# New code formatting tool
@tool
def format_code_tool(code: str) -> str:
    """
    Format code using black.
    :param code: The code to be formatted
    :return: The formatted code
    """
    try:
        return black.format_str(code, mode=black.FileMode())
    except black.NothingChanged:
        return code  # Return the original code if it is already formatted
    except Exception as e:
        return f"Error formatting code: {str(e)}"

# 测试
if __name__ == "__main__":
    start_time = time.time()
    
    # test
    namespace = "mistune.src.toc.add_toc_hook"
    print(code_search_tool.invoke(namespace))
    print(related_code_tool.invoke(namespace))
    
