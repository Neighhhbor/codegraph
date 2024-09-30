import networkx as nx
import re
from typing import List, Dict, Any


# 辅助函数: 获取目标节点和父节点
def find_target_node_and_parent(codegraph: nx.DiGraph, node_label: str) -> (str, str):
    """根据 node_label 定位目标节点和其父节点"""
    if node_label not in codegraph.nodes:
        raise ValueError(f"未找到指定的目标节点: {node_label}")
    
    # 查找父节点
    for parent, child, edge_data in codegraph.edges(data=True):
        if edge_data.get('relationship') == 'CONTAINS' and child == node_label:
            return child, parent  # 返回目标节点（child）和父节点
    raise ValueError(f"未找到父节点 for {node_label}")


# 辅助函数: 查找模块祖先节点
def find_module_ancestor(codegraph: nx.DiGraph, node_label: str) -> str:
    """递归查找目标节点的祖先模块节点"""
    parts = node_label.split('.')
    for i in range(len(parts), 0, -1):
        current_prefix = '.'.join(parts[:i])
        if current_prefix in codegraph.nodes and codegraph.nodes[current_prefix].get('type') == 'module':
            return current_prefix
    raise ValueError(f"未找到模块节点 (module) for {node_label}")


# 辅助函数: 提取模块导入语句
def extract_import_statements(codegraph: nx.DiGraph, module_node: str) -> str:
    """
    提取指定模块中的导入信息，包括 import 语句、全局变量、常量，直到遇到第一个函数定义。
    :param codegraph: NetworkX 图对象
    :param module_node: 模块节点的名称
    :return: 提取到的导入信息
    """
    file_code = codegraph.nodes[module_node].get('code', '')
    
    # 使用正则匹配所有在第一个函数定义（def）之前的内容
    import_lines = []
    for line in file_code.splitlines():
        if re.match(r'^\s*(def|class)\s+', line):
            break  # 遇到函数或类定义时，停止提取
        import_lines.append(line)  # 收集所有内容，包括 import、全局变量、常量等

    return "\n".join(import_lines)


# 辅助函数: 获取上下文节点
def get_context_siblings(codegraph: nx.DiGraph, target_node: str, parent_node: str, context_type: str) -> List[Dict[str, Any]]:
    """
    获取目标节点的上下文节点，返回上下文列表。
    :param codegraph: NetworkX 图对象
    :param target_node: 当前节点
    :param parent_node: 父节点
    :param context_type: "above" 或 "below"，指定上下文的方向
    :return: 包含兄弟节点的上下文列表
    """
    siblings = []
    target_found = False
    
    # 获取父节点的所有子节点（兄弟节点）
    for _, child, edge_data in codegraph.edges(parent_node, data=True):
        if edge_data.get('relationship') == 'CONTAINS':
            siblings.append(child)
    
    context_nodes = []
    for sibling in siblings:
        sibling_info = {'node_name': sibling, 'code': codegraph.nodes[sibling].get('code', 'No code available')}
        
        if sibling == target_node:
            target_found = True
            continue
        
        if context_type == "above" and not target_found:
            context_nodes.append(sibling_info)
        elif context_type == "below" and target_found:
            context_nodes.append(sibling_info)

    return context_nodes


# 辅助函数: 获取涉及的模块、类、方法等名称
def get_involved_names(node_label: str, codegraph: nx.DiGraph) -> Dict[str, str]:
    """
    获取涉及的模块、类、方法的名称
    :param node_label: 目标节点的标签
    :param codegraph: NetworkX 图对象
    :return: 包含模块、类和函数名称的字典
    """
    parts = node_label.split('.')
    result = {}
    for i in range(len(parts), 0, -1):
        current_prefix = '.'.join(parts[:i])
        if current_prefix in codegraph.nodes:
            node_type = codegraph.nodes[current_prefix].get('type')
            if node_type == 'module':
                result['module'] = current_prefix
            elif node_type == 'class':
                result['class'] = current_prefix
            elif node_type == 'function':
                result['function'] = current_prefix
    return result
