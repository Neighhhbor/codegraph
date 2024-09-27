import re
import networkx as nx
from langchain.tools import tool
from typing import List, Dict, Any

# 加载 NetworkX 图
def load_and_fix_gml(path: str) -> nx.DiGraph:
    """加载并修复 GML 文件中的特殊字符"""
    graph = nx.read_gml(path)
    for node in graph.nodes(data=True):
        for key, value in node[1].items():
            if isinstance(value, str):
                node[1][key] = value.replace('&#10;', '\n')
    return graph

# 调用这个函数来读取和处理 GML 文件
codegraph = load_and_fix_gml("/home/sxj/Desktop/Workspace/CodeQl/gptgraph/CodeGraph/results/code_graph.gml")

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

# 工具1: 获取上文（每次调用返回一个节点）
@tool
def get_context_above(node_label: str) -> Dict[str, Any]:
    """根据 node_label 获取该节点的上文（上方的代码上下文）"""
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)
    
    # 初始化上下文索引
    if node_label not in context_index:
        context_index[node_label] = {"above_index": 0, "below_index": 0}

    # 获取所有上文节点
    context_above = get_context_siblings(codegraph, target_node, parent_node, "above")
    
    # 获取当前的上文节点
    idx = context_index[node_label]["above_index"]
    if idx < len(context_above):
        context_index[node_label]["above_index"] += 1
        return context_above[idx]
    else:
        return {"message": "No more context above."}

# 工具2: 获取下文（每次调用返回一个节点）
@tool
def get_context_below(node_label: str) -> Dict[str, Any]:
    """根据 node_label 获取该节点的下文（下方的代码上下文）"""
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)
    
    # 初始化上下文索引
    if node_label not in context_index:
        context_index[node_label] = {"above_index": 0, "below_index": 0}

    # 获取所有下文节点
    context_below = get_context_siblings(codegraph, target_node, parent_node, "below")
    
    # 获取当前的下文节点
    idx = context_index[node_label]["below_index"]
    if idx < len(context_below):
        context_index[node_label]["below_index"] += 1
        return context_below[idx]
    else:
        return {"message": "No more context below."}

# 工具3: 提取导入语句
@tool
def get_import_statements(node_label: str) -> Dict[str, str]:
    """根据 node_label 提取该节点所属模块中的导入语句"""
    module_node = find_module_ancestor(codegraph, node_label)
    return {"import_statements": extract_import_statements(module_node)}

# 工具4: 获取涉及的模块、类、方法等名称
@tool
def get_involved_names(node_label: str) -> Dict[str, str]:
    """根据 node_label 提取模块、类、方法等相关名称"""
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

# 工具5: 查找 one-hop 调用关系节点
@tool
def find_one_hop_call_nodes(node_label: str) -> List[Dict[str, Any]]:
    """查找与目标节点有调用关系的 one-hop 节点，返回其代码"""
    one_hop_nodes = []
    for parent, child, edge_data in codegraph.edges(data=True):
        if edge_data.get('relationship') == 'CALLS':
            if parent == node_label:
                one_hop_nodes.append({
                    "relationship": "CALLS",
                    "direction": "outgoing",
                    "target_node": child,
                    "target_node_code": codegraph.nodes[child].get('code', 'No code available')
                })
            elif child == node_label:
                one_hop_nodes.append({
                    "relationship": "CALLS",
                    "direction": "incoming",
                    "target_node": parent,
                    "target_node_code": codegraph.nodes[parent].get('code', 'No code available')
                })
    return one_hop_nodes

# 测试函数
if __name__ == "__main__":
    test_node_label = "stellar.stellar.app.Stellar.load_config"

    # 测试获取上文的工具
    print("获取上文:")
    print(get_context_above(test_node_label))
    print(get_context_above(test_node_label))

    # 测试获取下文的工具
    print("获取下文:")
    print(get_context_below(test_node_label))
    print(get_context_below(test_node_label))

    # 测试提取导入语句
    print("提取导入语句:", get_import_statements(test_node_label))

    # 测试获取涉及的名称
    print("获取涉及的名称:", get_involved_names(test_node_label))

    # 测试 find_one_hop_call_nodes 工具
    print("One-hop 调用关系的节点:")
    for node in find_one_hop_call_nodes(test_node_label):
        print(node)
