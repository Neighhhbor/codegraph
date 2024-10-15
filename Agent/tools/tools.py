import os
import sys
import time
from tqdm import tqdm
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import torch
import torch.nn as nn
import psutil
import socket

# 设置可见的 CUDA 设备为 2 和 3
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
# 设置 HuggingFace 镜像站点
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# 使用相对路径添加项目根目录到 Python 搜索路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

import networkx as nx
import json
from utils import *
from Agent.tools.replace_data import replace_groundtruth_code_with_treesitter
from langchain_community.tools.riza.command import ExecPython
from typing import List, Dict, Any
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
import black
from embedding.semantic_analyzer import SemanticAnalyzer
from Agent.tools.model_server import start_model_server, stop_model_server, MODEL_SERVER_PORT
import atexit

class CodeGraphToolsWrapper:
    def __init__(self, graph_path: str, target_function: str):
        """
        初始化工具类，加载图数据、替换 ground truth 并存储状态
        :param graph_path: 图数据的路径
        :param target_function: 待替换 ground truth 的目标函数
        """
        self.graph_path = graph_path
        self.codegraph = self._load_and_process_graph(target_function)
        self.embeddings_path = self._get_embeddings_path()
        self.function_embeddings = self._load_or_create_embeddings()
        
        # 检查模型服务是否已经运行，如果没有则启动
        if not self.is_model_server_running():
            print("模型服务未运行，正在启动...")
            start_model_server()
            time.sleep(10)  # 给服务一些启动时间
        else:
            print("模型服务已经在运行中")

    def is_model_server_running(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', MODEL_SERVER_PORT))
                s.sendall(b'status')
                response = s.recv(1024)
                return response == b'running'
        except ConnectionRefusedError:
            return False

    def _get_embeddings_path(self):
        # 为每个图创建一个唯一的嵌入文件路径
        base_name = os.path.basename(self.graph_path)
        embeddings_dir = os.path.join(os.path.dirname(os.path.dirname(self.graph_path)), 'embeddings')
        
        # 确保 embeddings 目录存在
        os.makedirs(embeddings_dir, exist_ok=True)
        
        return os.path.join(embeddings_dir, f"{base_name}_embeddings.npz")

    def _load_or_create_embeddings(self):
        if os.path.exists(self.embeddings_path):
            print("加载现有的嵌入...")
            return np.load(self.embeddings_path, allow_pickle=True)
        else:
            print("创建新的嵌入...")
            return self._create_and_save_embeddings()

    def _create_and_save_embeddings(self):
        functions = [(n, d) for n, d in self.codegraph.nodes(data=True) if d['type'] == 'function']
        
        embeddings = {}
        for node, data in tqdm(functions, desc="生成函数嵌入"):
            code = data.get('code', '')
            embedding = self.get_embedding(code)
            embeddings[node] = embedding

        np.savez(self.embeddings_path, **embeddings)
        return embeddings

    def _load_and_process_graph(self, target_function: str) -> nx.DiGraph:
        """
        加载图并使用 replace_data 替换 ground truth。
        :param target_function: 需要替换的目标函数名称
        :return: 处理后的图数据
        """
        if os.path.exists(self.graph_path):
            with open(self.graph_path, 'r') as f:
                data = json.load(f)
            graph = nx.node_link_graph(data)
            
            # 调用 replace_data 来替换 ground truth
            replace_groundtruth_code_with_treesitter(graph, target_function)
            
            return graph
        else:
            raise FileNotFoundError(f"Code graph not found at {self.graph_path}")

    def get_context_above(self, node_label: str) -> Dict[str, Any]:
        """获取目标节点上文"""
        target_node, parent_node = find_target_node_and_parent(self.codegraph, node_label)
        context_above = get_context_siblings(self.codegraph, target_node, parent_node, "above")
        
        if context_above:
            return {"context_above": context_above}
        else:
            return {"message": "No more context above."}

    def get_context_below(self, node_label: str) -> Dict[str, Any]:
        """获取目标节点下文"""
        target_node, parent_node = find_target_node_and_parent(self.codegraph, node_label)
        context_below = get_context_siblings(self.codegraph, target_node, parent_node, "below")
        
        if context_below:
            return {"context_below": context_below}
        else:
            return {"message": "No more context below."}

    def get_import_statements(self, node_label: str) -> Dict[str, str]:
        """提取导入语句"""
        module_node = find_module_ancestor(self.codegraph, node_label)
        return {"import_statements": extract_import_statements(self.codegraph, module_node)}

    def get_involved_names(self, node_label: str) -> Dict[str, str]:
        """获取涉及的模块、类、方法等名称"""
        return get_involved_names(node_label, self.codegraph)

    def find_one_hop_call_nodes(self, node_label: str) -> List[Dict[str, Any]]:
        """查找 one-hop 调用关系节点"""
        one_hop_nodes = []
        for parent, child, edge_data in self.codegraph.edges(data=True):
            if edge_data.get('relationship') == 'CALLS':
                if parent == node_label:
                    target_node_code = self.codegraph.nodes[child].get('code', 'No code available')
                    one_hop_nodes.append({
                        "relationship": "CALLS",
                        "direction": "outgoing",
                        "target_node": child,
                        "target_node_code": target_node_code
                    })
                elif child == node_label:
                    target_node_code = self.codegraph.nodes[parent].get('code', 'No code available')
                    one_hop_nodes.append({
                        "relationship": "CALLS",
                        "direction": "incoming",
                        "target_node": parent,
                        "target_node_code": target_node_code
                    })
        return one_hop_nodes

    def get_node_info(self, node_label: str) -> Dict[str, Any]:
        """获取节点的详细信息"""
        if node_label not in self.codegraph.nodes:
            return {"message": f"Node {node_label} not found in the graph."}
        
        node_info = self.codegraph.nodes[node_label]
        return {"node_info": node_info}

    def get_embedding(self, text):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', MODEL_SERVER_PORT))
                s.sendall(f"embed:{text}".encode())
                response = s.recv(4096)  # 假设嵌入向量不会超过4096字节
                return np.frombuffer(response, dtype=np.float32)
        except Exception as e:
            print(f"获取嵌入向量时出错: {e}")
            return None

    def find_most_similar_function(self, query_function: str):
        if not self.is_model_server_running():
            print("模型服务未运行，正在重新启动...")
            start_model_server()
            time.sleep(10)  # 给服务一些启动时间
        
        query_embedding = self.get_embedding(query_function)
        if query_embedding is None:
            return {"message": "无法获取查询函数的嵌入向量。"}

        max_similarity = -1
        most_similar_node = None

        for node, embedding in self.function_embeddings.items():
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_node = node

        if most_similar_node:
            node_data = self.codegraph.nodes[most_similar_node]
            return {
                "node_label": most_similar_node,
                "similarity": max_similarity,
                "code": node_data.get('code', ''),
                "type": node_data.get('type', ''),
                "name": node_data.get('name', '')
            }
        else:
            return {"message": "未找到相似函数。"}


# 将工具类包裹成 langchain 的工具
def create_tools(graph_path: str, target_function: str):
    wrapper = CodeGraphToolsWrapper(graph_path, target_function)

    @tool
    def get_context_above_tool(node_label: str) -> Dict[str, Any]:
        """取上文"""
        return wrapper.get_context_above(node_label)

    @tool
    def get_context_below_tool(node_label: str) -> Dict[str, Any]:
        """获取下文"""
        return wrapper.get_context_below(node_label)

    @tool
    def get_import_statements_tool(node_label: str) -> Dict[str, str]:
        """提取导入语句"""
        return wrapper.get_import_statements(node_label)

    @tool
    def get_involved_names_tool(node_label: str) -> Dict[str, str]:
        """获取涉及的名称"""
        return wrapper.get_involved_names(node_label)

    @tool
    def find_one_hop_call_nodes_tool(node_label: str) -> List[Dict[str, Any]]:
        """查找 one-hop 调用关系节点"""
        return wrapper.find_one_hop_call_nodes(node_label)

    @tool
    def get_node_info_tool(node_label: str) -> Dict[str, Any]:
        """获取节点详细信息"""
        return wrapper.get_node_info(node_label)

    @tool
    def find_most_similar_function_tool(query_function: str) -> Dict[str, Any]:
        """找到与给定函数最相似的函数"""
        return wrapper.find_most_similar_function(query_function)

    # 新增 DuckDuckGo 搜索工具
    @tool
    def duckduckgo_search_tool(query: str) -> str: 
        """使用 DuckDuckGo 进行网络搜索并总结结果"""
        search = DuckDuckGoSearchRun()
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)  # 使用 GPT-4 作为 LLM
        
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

    # 新增代码格式化工具
    @tool
    def format_code_tool(code: str) -> str:
        """使用 black 格式化代码"""
        try:
            return black.format_str(code, mode=black.FileMode())
        except black.NothingChanged:
            return code  # 果代码已格式化，返回原代码
        except Exception as e:
            return f"Error formatting code: {str(e)}"
    
    @tool
    def execute_python_code(code: str) -> str:
        """执行 Python 代码并通过 Riza 返回结果"""
        try:
            # 初始化 ExecPython 工具
            exec_tool = ExecPython()
            
            # 调用 Riza 的 ExecPython 工具来执行代码
            result = exec_tool.invoke({"code": code})
            
            # 从 Riza 的响应中提取结果
            if "output" in result and result["output"]:
                return result["output"][0]["text"]
            else:
                return "Execution completed, but no output was returned."
        
        except Exception as e:
            # 捕获并返回任何异常信息
            return f"Error during code execution: {str(e)}"

    # 返回所有工具供 agent 使用
    return [
        get_context_above_tool,
        get_context_below_tool,
        get_import_statements_tool,
        get_involved_names_tool,
        find_one_hop_call_nodes_tool,
        get_node_info_tool,
        duckduckgo_search_tool,
        format_code_tool,
        execute_python_code,
        find_most_similar_function_tool
    ]


# 测试
if __name__ == "__main__":
    start_time = time.time()
    
    print("检查模型服务是否运行...")
    wrapper = CodeGraphToolsWrapper("/home/shixianjie/codegraph/codegraph/data_process/graphs/mistune.json", "mistune.src.mistune.toc.add_toc_hook")
    
    graph_path = "/home/shixianjie/codegraph/codegraph/data_process/graphs/mistune.json"
    target_function = "mistune.src.mistune.toc.add_toc_hook"
    
    print("开始创建工具")
    tools = create_tools(graph_path, target_function)

    # 测试工具
    test_node_label = "mistune.src.mistune.toc.add_toc_hook"

    # 测试所有工具
    print("测试获取上文工具:")
    print(tools[0](test_node_label))

    print("\n试获取下文工具:")
    print(tools[1](test_node_label))

    print("\n测试获取导入语句工具:")
    print(tools[2](test_node_label))

    print("\n测试获取涉及的名称工具:")
    print(tools[3](test_node_label))

    print("\n测试查找 one-hop 调用关系节点工具:")
    print(tools[4](test_node_label))

    print("\n测试获取节点详细信息工具:")
    print(tools[5](test_node_label))

    # print("\n测试 DuckDuckGo 搜索工具:")
    # print(tools[6]("Python programming"))

    print("\n测试代码格式化工具:")
    test_code = "def test_function(x,y):\n  return x+y"
    print(tools[7](test_code))

    print("\n测试执行 Python 代码工具:")
    test_exec_code = "print('Hello, World!')"
    print(tools[8](test_exec_code))

    print("\n测试查找最相似函数工具:")
    test_query_function = "def add_numbers(a, b):\n    return a + b"
    print(tools[9](test_query_function))

    end_time = time.time()
    print(f"总执行时间: {end_time - start_time:.2f} 秒")

    print("测试完成，程序即将退出。")
    print("注意：模型服务仍在后台运行。如需停止，请手动终止 start_model_server.py 进程。")

    # 确保所有资源都被释放
    import gc
    gc.collect()

    # 强制退出程序
    import os
    os._exit(0)