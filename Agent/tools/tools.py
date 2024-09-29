import re
import networkx as nx
from langchain.tools import tool
from typing import List, Dict, Any

# 图加载装饰器
from utils import *

# 工具1: 获取上文（每次调用返回一个节点）
@tool
@with_graph_loading  # 添加图加载装饰器
def get_context_above(codegraph: nx.DiGraph, node_label: str, context_index: Dict[str, Any]) -> Dict[str, Any]:
    """根据 node_label 获取该节点的上文（上方的代码上下文）"""
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)

    # 初始化上下文索引
    if node_label not in context_index:
        context_index[node_label] = {"above_index": 0, "below_index": 0}

    # 获取所有上文节点
    context_above = get_context_siblings(codegraph, target_node, parent_node, "above")

    # 获取当前的上文节点，并更新索引
    idx = context_index[node_label]["above_index"]
    if idx < len(context_above):
        context_index[node_label]["above_index"] += 1
        return context_above[idx]
    else:
        return {"message": "No more context above."}

# 工具2: 获取下文
@tool
@with_graph_loading
def get_context_below(codegraph: nx.DiGraph, node_label: str, context_index: Dict[str, Any]) -> Dict[str, Any]:
    """根据 node_label 获取该节点的下文（下方的代码上下文）"""
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)

    # 初始化上下文索引
    if node_label not in context_index:
        context_index[node_label] = {"above_index": 0, "below_index": 0}

    # 获取所有下文节点
    context_below = get_context_siblings(codegraph, target_node, parent_node, "below")

    # 获取当前的下文节点，并更新索引
    idx = context_index[node_label]["below_index"]
    if idx < len(context_below):
        context_index[node_label]["below_index"] += 1
        return context_below[idx]
    else:
        return {"message": "No more context below."}

# 工具3: 提取导入语句
@tool
@with_graph_loading
def get_import_statements(codegraph: nx.DiGraph, node_label: str) -> Dict[str, str]:
    """根据 node_label 提取该节点所属模块中的导入语句"""
    module_node = find_module_ancestor(codegraph, node_label)
    return {"import_statements": extract_import_statements(module_node)}

# 工具4: 获取涉及的模块、类、方法等名称
@tool
@with_graph_loading
def get_involved_names(codegraph: nx.DiGraph, node_label: str) -> Dict[str, str]:
    """根据 node_label 提取模块、类、方法等相关名称"""
    return parse_involved_names(codegraph, node_label)

# 工具5: 查找 one-hop 调用关系节点
@tool
@with_graph_loading
def find_one_hop_call_nodes(codegraph: nx.DiGraph, node_label: str) -> Dict[str, Any]:
    """查找与目标节点有调用关系的 one-hop 节点，返回其代码"""
    return find_related_call_nodes(codegraph, node_label)



# 测试函数
if __name__ == "__main__":
    test_node_label = "stellar.stellar.app.Stellar.load_config"

    # 测试获取上文的工具
    print("获取上文:")
    print(get_context_above(test_node_label))

    # 测试获取下文的工具
    print("获取下文:")
    print(get_context_below(test_node_label))

    # 测试提取导入语句
    print("提取导入语句:", get_import_statements(test_node_label))

    # 测试获取涉及的名称
    print("获取涉及的名称:", get_involved_names(test_node_label))

    # 测试 find_one_hop_call_nodes 工具
    print("One-hop 调用关系的节点:")
    for node in find_one_hop_call_nodes(test_node_label):
        print(node)
