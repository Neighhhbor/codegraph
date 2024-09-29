from langchain.tools import tool
from utils import *


# 工具1: 获取上文（一次性返回所有上文节点）
@tool
def get_context_above(node_label: str) -> Dict[str, Any]:
    """Use this tool to get the code context above the current function."""
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)
    context_above = get_context_siblings(codegraph, target_node, parent_node, "above")
    
    if context_above:
        return {"context_above": context_above}
    else:
        return {"message": "No more context above."}

# 工具2: 获取下文（一次性返回所有下文节点）
@tool
def get_context_below(node_label: str) -> Dict[str, Any]:
    """Use this tool to retrieve the code context below the function."""
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)
    context_below = get_context_siblings(codegraph, target_node, parent_node, "below")
    
    if context_below:
        return {"context_below": context_below}
    else:
        return {"message": "No more context below."}

# 工具3: 提取导入语句
@tool
def get_import_statements(node_label: str) -> Dict[str, str]:
    """Retrieve the import statements of the module where the function is located."""
    module_node = find_module_ancestor(codegraph, node_label)
    return {"import_statements": extract_import_statements(module_node)}

# 工具4: 获取涉及的模块、类、方法等名称
@tool
def get_involved_names(node_label: str) -> Dict[str, str]:
    """get the related class and module name of the target node"""
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
    """This tool can be used to identify related function nodes by finding one-hop call relationships."""
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

# 工具6: 获取节点的详细信息
@tool
def get_node_info(node_label: str) -> Dict[str, Any]:
    """Retrieve the detailed information (attributes) of a specific node retrieved in the graph."""
    # 检查节点是否存在
    if node_label not in codegraph.nodes:
        return {"message": f"Node {node_label} not found in the graph."}
    
    # 获取节点属性
    node_info = codegraph.nodes[node_label]
    
    return {"node_info": node_info}

# 测试函数
if __name__ == "__main__":
    test_node_label = "whereami.whereami.predict.crossval"

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
