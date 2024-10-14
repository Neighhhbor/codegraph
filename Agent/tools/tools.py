import os
import sys
# 增加import路径
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"
sys.path.append('/home/sxj/Desktop/Workspace/CodeQl/gptgraph')

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


class CodeGraphToolsWrapper:
    def __init__(self, graph_path: str, target_function: str):
        """
        初始化工具类，加载图数据、替换 ground truth 并存储状态
        :param graph_path: 图数据的路径
        :param target_function: 待替换 ground truth 的目标函数
        """
        self.graph_path = graph_path
        self.codegraph = self._load_and_process_graph(target_function)
        self.semantic_analyzer = SemanticAnalyzer()

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

    def find_most_similar_function(self, query_function: str):
        functions = [(n, d) for n, d in self.codegraph.nodes(data=True) if d['type'] == 'function']
        query_embedding = self.semantic_analyzer.embed_code(query_function)
        
        max_similarity = -1
        most_similar_node = None
        
        for node, data in functions:
            code = data.get('code', '')
            node_embedding = self.semantic_analyzer.embed_code(code)
            similarity = self.semantic_analyzer.calculate_similarity(query_embedding, node_embedding)
            
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
            return {"message": "No similar function found."}


# 将工具类包裹成 langchain 的工具
def create_tools(graph_path: str, target_function: str):
    wrapper = CodeGraphToolsWrapper(graph_path, target_function)

    @tool
    def get_context_above_tool(node_label: str) -> Dict[str, Any]:
        """获取上文"""
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
        """使用 DuckDuckGo 进��网络搜索并总结结果"""
        search = DuckDuckGoSearchRun()
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)  # 使用 GPT-4 作为 LLM
        
        try:
            # 使用 DuckDuckGo 进行搜索
            search_results = search.invoke(query)
            
            # 如果没有搜索结果，返回默认信息
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
            return code  # 如果代码已格式化，返回原代码
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
    graph_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs/mistune.json"
    target_function = "mistune.src.mistune.toc.add_toc_hook"
    
    tools = create_tools(graph_path, target_function)

    # 测试工具
    test_node_label = "mistune.src.mistune.toc.add_toc_hook"

    # 测试所有工具
    print("测试获取上文工具:")
    print(tools[0](test_node_label))

    print("\n测试获取下文工具:")
    print(tools[1](test_node_label))

    print("\n测试获取导入语句工具:")
    print(tools[2](test_node_label))

    print("\n测试获取涉及的名称工具:")
    print(tools[3](test_node_label))

    print("\n测试查找 one-hop 调用关系节点工具:")
    print(tools[4](test_node_label))

    print("\n测试获取节点详细信息工具:")
    print(tools[5](test_node_label))

    print("\n测试 DuckDuckGo 搜索工具:")
    print(tools[6]("Python programming"))

    print("\n测试代码格式化工具:")
    test_code = "def test_function(x,y):\n    return x+y"
    print(tools[7](test_code))

    print("\n测试执行 Python 代码工具:")
    test_exec_code = "print('Hello, World!')"
    print(tools[8](test_exec_code))

    print("\n测试查找最相似函数工具:")
    test_query_function = "def add_numbers(a, b):\n    return a + b"
    print(tools[9](test_query_function))
