import re
import networkx as nx
from langchain.tools import tool
from typing import List, Dict, Any

# 加载 NetworkX 图
def load_and_fix_gml(path):
    graph = nx.read_gml(path)
    # 修复节点中的 &#10; 为 \n
    for node in graph.nodes(data=True):
        for key, value in node[1].items():
            if isinstance(value, str):
                node[1][key] = value.replace('&#10;', '\n')
    return graph

# 调用这个函数来读取和处理 GML 文件
codegraph = load_and_fix_gml("/home/sxj/Desktop/Workspace/CodeQl/gptgraph/CodeGraph/results/code_graph.gml")

# 工具1: 获取上文
@tool
def get_context_above(node_label: str) -> Any:
    """
    根据 node_label 获取该节点的上文（上方的代码上下文）。
    """
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)
    context_above = []
    for context_node in get_context_siblings(codegraph, target_node, parent_node, "above"):
        context_above.append(context_node)
    return context_above

# 工具2: 获取下文
@tool
def get_context_below(node_label: str) -> Any:
    """
    根据 node_label 获取该节点的下文（下方的代码上下文）。
    """
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)
    context_below = []
    for context_node in get_context_siblings(codegraph, target_node, parent_node, "below"):
        context_below.append(context_node)
    return context_below

# 工具3: 提取导入语句
@tool
def get_import_statements(node_label: str) -> Any:
    """
    根据 node_label 提取该节点所属模块中的导入语句（import 部分）。
    """
    module_node = find_module_ancestor(codegraph, node_label)
    import_statements = extract_import_statements(module_node)
    return {"import_statements": import_statements}

# 工具4: 获取涉及的模块、类、方法等名称
@tool
def get_involved_names(node_label: str) -> Any:
    """
    根据 node_label 提取模块、类、方法等相关名称。
    """
    involved_names = parse_node_label(node_label, codegraph)
    return {"involved_names": involved_names}

# 工具5: 获取BM25相关结果
@tool
def get_bm25_results_tool(node_label: str) -> Any:
    """
    根据 node_label 获取 BM25 算法计算的相关结果（占位符实现）。
    """
    bm25_results = get_bm25_results(node_label)
    return {"bm25_results": bm25_results}

# 获取目标节点和父节点的辅助函数
def find_target_node_and_parent(codegraph, node_label):
    target_node = node_label
    if target_node not in codegraph.nodes:
        raise ValueError(f"未找到指定的目标函数节点: {node_label}")
    parent_node = None
    for parent, child, edge_data in codegraph.edges(data=True):
        if edge_data.get('relationship') == 'CONTAINS' and child == target_node:
            parent_node = parent
            break
    if parent_node is None:
        raise ValueError(f"未找到父节点 (文件) for {node_label}")
    return target_node, parent_node

# 获取上下文节点的辅助函数，逐步返回上下文节点
def get_context_siblings(codegraph, target_node, parent_node, context_type):
    siblings = []
    target_found = False
    for parent, child, edge_data in codegraph.edges(parent_node, data=True):
        if edge_data.get('relationship') == 'CONTAINS':
            siblings.append(child)
    for sibling in siblings:
        sibling_info = {'node_name': sibling}
        sibling_info.update(codegraph.nodes[sibling])  # 获取节点的属性
        if sibling == target_node:
            target_found = True
            continue
        if context_type == "above" and not target_found:
            sibling_info['context'] = 'above'
            yield sibling_info
        elif context_type == "below" and target_found:
            sibling_info['context'] = 'below'
            yield sibling_info

# 递归查找模块祖先节点
def find_module_ancestor(codegraph, node_label: str) -> str:
    parts = node_label.split('.')
    for i in range(len(parts), 0, -1):
        current_prefix = '.'.join(parts[:i])
        if current_prefix in codegraph.nodes and codegraph.nodes[current_prefix].get('type') == 'module':
            return current_prefix
    raise ValueError(f"未找到模块节点 (module) for {node_label}")

# 提取模块导入语句
def extract_import_statements(module_node: str) -> str:
    """
    提取指定模块（文件）中的导入信息，包括import语句、全局变量、常量，直到遇到第一个函数定义。
    :param module_node: 模块节点的名称
    :return: 提取到的导入信息
    """
    file_code = codegraph.nodes[module_node].get('code', '')
    
    # 使用正则匹配所有在第一个函数定义（def）之前的内容
    import_lines = []
    inside_import_block = True
    for line in file_code.splitlines():
        # 如果遇到函数定义时，停止提取
        if re.match(r'^\s*def\s+', line):
            break
        # 收集所有内容，包括import、全局变量、常量等
        import_lines.append(line)

    return "\n".join(import_lines)

# 解析 node_label
def parse_node_label(node_label: str, codegraph: nx.DiGraph) -> Dict[str, str]:
    parts = node_label.split('.')
    result = {}
    for i in range(len(parts), 0, -1):
        current_prefix = '.'.join(parts[:i])
        if current_prefix in codegraph.nodes:
            node_type = codegraph.nodes[current_prefix].get('type')
            if node_type == 'module':
                result['module'] = current_prefix
                break
            if node_type == "class":
                result['class'] = current_prefix
            if node_type == "function":
                result['function'] = current_prefix
    return result

# 获取BM25相关结果
def get_bm25_results(node_label: str) -> List[str]:
    return ["result1", "result2"]

if __name__ == "__main__":
    test_node_label = "stellar.stellar.app.Stellar.load_config"

    # 测试获取上文的生成器
    context_above_generator = get_context_above(test_node_label,0)
    print("获取上文:")
    for batch in context_above_generator:
        print(batch)

    # 测试获取下文的生成器
    context_below_generator = get_context_below(test_node_label, 0)
    print("获取下文:")
    for batch in context_below_generator:
        print(batch)

    # 测试提取导入语句
    print("提取导入语句:", get_import_statements(test_node_label))

    # 测试获取涉及的名称
    print("获取涉及的名称:", get_involved_names(test_node_label))

    # 测试 BM25 相关结果
    print("BM25相关结果:", get_bm25_results_tool(test_node_label))
