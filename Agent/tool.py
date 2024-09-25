import re
import networkx as nx
from langchain.tools import tool
from typing import List, Dict, Any


# 加载 NetworkX 图
codegraph = nx.read_gml("/home/sxj/Desktop/Workspace/CodeQl/gptgraph/CodeGraph/results/code_graph.gml")


@tool
def find_anchors(node_label: str) -> List[Dict[str, Any]]:
    """
    提供一个工具，用于根据 node_label 查找相关锚点信息。
    查找的信息包括上文、下文、导入模块以及涉及的名称。
    """
    anchors = []

    # 定位目标节点及其父节点（文件）
    target_node, parent_node = find_target_node_and_parent(codegraph, node_label)

    # 获取上文和下文
    context_above, context_below = get_context_siblings(codegraph, target_node, parent_node)
    anchors.append({"context_above": context_above})
    anchors.append({"context_below": context_below})

    # 提取文件中的导入模块
    file_code = codegraph.nodes[parent_node].get('code', '')
    imported_modules = get_imported_modules(file_code)
    anchors.append({"imported_modules": imported_modules})

    # 解析 node_label 提取模块、类、方法等名称
    involved_names = parse_node_label(node_label, codegraph)
    anchors.append({"involved_names": involved_names})

    # 暂时的占位符，bm25相关逻辑可以替换成实际实现
    bm25_results = get_bm25_results(node_label)
    anchors.append({"bm25_results": bm25_results})

    return anchors


# 获取目标节点和父节点的辅助函数
def find_target_node_and_parent(codegraph, node_label):
    """
    定位给定 node_label 的目标函数节点，并找到它的父节点（文件）。
    """
    target_node = node_label  # 使用 node_label 直接作为目标节点的 fullname
    if target_node not in codegraph.nodes:
        raise ValueError(f"未找到指定的目标函数节点: {node_label}")
    
    # 查找父节点 (文件)
    parent_node = None
    for parent, child, edge_data in codegraph.edges(data=True):
        if edge_data.get('relationship') == 'CONTAINS' and child == target_node:
            parent_node = parent
            break
    
    if parent_node is None:
        raise ValueError(f"未找到父节点 (文件) for {node_label}")
    
    return target_node, parent_node


# 获取上下文节点的辅助函数
def get_context_siblings(codegraph, target_node, parent_node):
    """
    获取目标节点的上下文节点（上文和下文）。
    """
    siblings = []
    context_above = []
    context_below = []
    target_found = False

    # 遍历父节点的所有子节点（siblings），找到目标节点的上文和下文
    for parent, child, edge_data in codegraph.edges(parent_node, data=True):
        if edge_data.get('relationship') == 'CONTAINS':
            siblings.append(child)

    # 遍历 siblings，确定上文和下文
    for sibling in siblings:
        sibling_info = {}
        sibling_info = {'node_name': sibling}
        # 获取节点的属性
        sibling_info.update(codegraph.nodes[sibling]) 

        if sibling == target_node:
            target_found = True
            continue
        
        if not target_found:
            # 在目标节点之前的所有兄弟节点都是上文
            context_above.append(sibling_info)
        else:
            # 在目标节点之后的所有兄弟节点都是下文
            context_below.append(sibling_info)
    
    return context_above, context_below


# 提取导入模块的辅助函数
def get_imported_modules(file_node_code: str) -> List[str]:
    """
    从文件节点的 code 字段中提取导入的模块信息。
    """
    # 正则表达式来匹配 import 语句和 from ... import 语句
    import_pattern = r'^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))'
    
    modules = set()
    for line in file_node_code.splitlines():
        match = re.match(import_pattern, line)
        if match:
            # from ... import ... 匹配的模块是 match.group(1)
            # import ... 匹配的模块是 match.group(2)
            module = match.group(1) or match.group(2)
            if module:
                modules.add(module)
    
    return list(modules)


# 解析 node_label 的辅助函数
def parse_node_label(node_label: str, codegraph: nx.DiGraph) -> Dict[str, str]:
    """
    解析 node_label，依次向前查找，直到找到第一个模块节点为止。
    :param node_label: 全局路径，例如 stellar.stellar.app.Stellar.load_config
    :param codegraph: NetworkX 图对象
    :return: 包含模块名的字典
    """
    parts = node_label.split('.')
    result = {}

    # 从完整路径逐步缩短，依次检查每个前缀
    for i in range(len(parts), 0, -1):
        current_prefix = '.'.join(parts[:i])

        # 查看当前前缀是否在图中
        if current_prefix in codegraph.nodes:
            node_type = codegraph.nodes[current_prefix].get('type')

            # 找到模块节点后停止
            if node_type == 'module':
                result['module'] = current_prefix
                break
            
            if node_type == "class" :
                result['class'] = current_prefix
            
            if node_type == "function":
                result['function'] = current_prefix

    return result




# 暂时的bm25结果函数，可以替换成实际实现
def get_bm25_results(node_label: str) -> List[str]:
    return ["result1", "result2"]


if __name__ == "__main__":
    # 假设我们已经有 find_anchors 工具和 codegraph 加载完成
    # node_label 是图中的某个节点全局路径

    # 定义一个测试的 node_label
    test_node_label = "stellar.stellar.app.Stellar.load_config"

    # 调用工具进行测试
    test_result = find_anchors(test_node_label)

    # 打印测试结果
    print("测试结果:")
    for anchor in test_result:
        print(anchor)
