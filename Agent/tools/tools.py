import os
import sys
# 增加import路径
sys.path.append('/home/sxj/Desktop/Workspace/CodeQl/gptgraph')

import networkx as nx
import json
from utils import *
from Agent.tools.replace_data import replace_groundtruth_code_with_treesitter

from typing import List, Dict, Any
from langchain.tools import tool


class CodeGraphToolsWrapper:
    def __init__(self, graph_path: str, target_function: str):
        """
        初始化工具类，加载图数据、替换 ground truth 并存储状态
        :param graph_path: 图数据的路径
        :param target_function: 待替换 ground truth 的目标函数
        """
        self.graph_path = graph_path
        self.codegraph = self._load_and_process_graph(target_function)

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

    # 返回所有工具供 agent 使用
    return [
        get_context_above_tool,
        get_context_below_tool,
        get_import_statements_tool,
        get_involved_names_tool,
        find_one_hop_call_nodes_tool,
        get_node_info_tool,
    ]


# 测试
if __name__ == "__main__":
    graph_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs/stellar.json"
    target_function = "stellar.stellar.models.Table.get_table_name"
    
    tools = create_tools(graph_path, target_function)

    # 测试工具
    test_node_label = "stellar.stellar.models.Table.get_table_name"

    # 测试工具
    print(tools[0](test_node_label))  # 获取上文
    print(tools[1](test_node_label))  # 获取下文
    print(tools[2](test_node_label))  # 获取导入语句
    print(tools[3](test_node_label))  # 获取涉及的名称
    print(tools[4](test_node_label))  # 获取 one-hop 调用节点
    print(tools[5](test_node_label))  # 获取节点详细信息
