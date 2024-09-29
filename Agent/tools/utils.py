import os
import networkx as nx
import re
from typing import List, Dict, Any


def load_graph_from_namespace(namespace: str, base_dir: str) -> nx.DiGraph:
    """根据 namespace 的第一个字段加载图文件"""
    graph_name = namespace.split('.')[0]  # 获取 namespace 的第一个字段
    graph_file = f"{graph_name}.gml"  # 构造图文件名
    graph_path = os.path.join(base_dir, graph_file)

    # 检查图文件是否存在
    if not os.path.exists(graph_path):
        raise FileNotFoundError(f"图文件 {graph_file} 不存在于目录 {base_dir}")

    # 加载并返回图
    return nx.read_gml(graph_path)

# 图加载装饰器
def with_graph_loading(func):
    """装饰器，用于在工具函数调用前动态加载图"""
    def wrapper(node_label: str, base_dir: str = "/path/to/gml/graphs", *args, **kwargs):
        namespace = node_label.split('.')[0]  # 从 node_label 提取 namespace
        graph = load_graph_from_namespace(namespace, base_dir)  # 加载图
        return func(graph, node_label, *args, **kwargs)  # 将图传递给工具函数
    return wrapper



# 测试示例
base_dirxectory = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs"  # 设置GML文件的路径
namespace = "stellar.stellar.config.save_config"  # 示例 namespace

# 加载与 namespace 对应的图

# 全局状态：记录每个 node_label 的上下文索引
context_index = {}

# 辅助函数: 获取目标节点和父节点
def find_target_node_and_parent(codegraph: nx.DiGraph, node_label: str) -> (str, str):
    """根据 node_label 定位目标节点和其父节点"""
    if node_label not in codegraph.nodes:
        raise ValueError(f"未找到指定的目标函数节点: {node_label}")
    
    # 查找父节点
    for parent, child, edge_data in codegraph.edges(data=True):
        if edge_data.get('relationship') == 'CONTAINS' and child == node_label:
            return node_label, parent
    raise ValueError(f"未找到父节点 (文件) for {node_label}")

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
def extract_import_statements(module_node: str) -> str:
    """
    提取指定模块（文件）中的导入信息，包括 import 语句、全局变量、常量，直到遇到第一个函数定义。
    :param module_node: 模块节点的名称
    :return: 提取到的导入信息
    """
    file_code = codegraph.nodes[module_node].get('code', '')
    
    # 使用正则匹配所有在第一个函数定义（def）之前的内容
    import_lines = []
    for line in file_code.splitlines():
        # 如果遇到函数定义时，停止提取
        if re.match(r'^\s*(def|class)\s+', line):
            break
        # 收集所有内容，包括 import、全局变量、常量等
        import_lines.append(line)

    return "\n".join(import_lines)

# 辅助函数: 获取上下文节点
def get_context_siblings(codegraph: nx.DiGraph, target_node: str, parent_node: str, context_type: str) -> List[Dict[str, Any]]:
    """获取目标节点的上下文节点，返回上下文列表"""
    siblings = []
    target_found = False
    
    # 获取父节点的所有子节点（兄弟节点）
    for _, child, edge_data in codegraph.edges(parent_node, data=True):
        if edge_data.get('relationship') == 'CONTAINS':
            siblings.append(child)
    
    context_nodes = []
    for sibling in siblings:
        sibling_info = {'node_name': sibling, **codegraph.nodes[sibling]}
        if sibling == target_node:
            target_found = True
            continue
        if context_type == "above" and not target_found:
            sibling_info['context'] = 'above'
            context_nodes.append(sibling_info)
        elif context_type == "below" and target_found:
            sibling_info['context'] = 'below'
            context_nodes.append(sibling_info)

    return context_nodes
