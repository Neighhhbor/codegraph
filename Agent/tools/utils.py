import os
import networkx as nx
from tree_sitter import Parser
from tree_sitter import Parser, Language
import tree_sitter_python as tspython


# 使用 Tree-sitter 解析代码
def parse_code_with_treesitter(code):
    """使用 Tree-sitter 解析 Python 代码"""
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)
    tree = parser.parse(bytes(code, "utf8"))
    return tree


def get_function_body(node, code):
    """根据 Tree-sitter 解析树，提取函数体"""
    # 找到函数体的开始和结束位置
    body_start_byte = node.children[4].start_byte  # 假设函数体为第5个子节点（需要根据语法树结构调整）
    body_end_byte = node.end_byte
    return code[body_start_byte:body_end_byte]


def replace_function_body(code, function_name):
    """
    使用 Tree-sitter 替换目标函数的函数体
    :param code: Python 代码字符串
    :param function_name: 需要替换函数体的函数名
    :return: 替换后的代码
    """
    tree = parse_code_with_treesitter(code)
    root_node = tree.root_node

    # 遍历语法树，找到目标函数
    for node in root_node.children:
        if node.type == 'function_definition':
            function_id = node.child_by_field_name('name')
            if function_id and function_id.text.decode('utf-8') == function_name:
                # 找到函数体并替换
                body = get_function_body(node, code)
                new_body = "<CODETOCOMPLETE>"
                start_byte = node.children[4].start_byte  # 函数体起始字节位置
                end_byte = node.end_byte  # 函数体结束字节位置

                # 替换函数体
                updated_code = code[:start_byte] + new_body + code[end_byte:]
                return updated_code
    return code  # 如果没有找到函数，则返回原始代码


# 示例函数，替换图中的目标函数体
def replace_groundtruth_code_with_treesitter(codegraph: nx.DiGraph, target_function: str):
    """
    使用 Tree-sitter 替换目标函数以及其父类和模块节点中的代码，将其函数体替换为 <CODETOCOMPLETE>。
    
    :param codegraph: NetworkX 图对象，包含代码节点
    :param target_function: 待补全的目标函数名称（如 'stellar.stellar.models.Table.get_table_name'）
    """
    function_name = target_function.split('.')[-1]  # 解析出函数名

    def replace_code_in_node(node_data):
        """在节点中替换目标函数体"""
        if "code" in node_data:
            code = node_data["code"]
            updated_code = replace_function_body(code, function_name)
            node_data["code"] = updated_code

    # 替换目标函数节点的代码
    if target_function in codegraph.nodes:
        replace_code_in_node(codegraph.nodes[target_function])

    # 查找并替换父类和模块节点中的代码
    current_node_label = target_function
    while current_node_label:
        _, parent_node_label = find_target_node_and_parent(codegraph, current_node_label)
        if parent_node_label:
            parent_node = codegraph.nodes[parent_node_label]
            replace_code_in_node(parent_node)
            # 如果父节点是模块类型，终止遍历
            if parent_node.get("type") == "module":
                break
            current_node_label = parent_node_label
        else:
            break


# 加载 NetworkX 图并修复 GML 文件中的特殊字符
def load_and_fix_gml(path: str) -> nx.DiGraph:
    """加载并修复 GML 文件中的特殊字符"""
    graph = nx.read_gml(path)
    return graph


if __name__ == "__main__":
    # 示例：在目标节点中替换代码
    gml_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs/stellar.gml"
    codegraph = load_and_fix_gml(gml_path)
    
    # 定义目标函数的名称
    target_function = "stellar.stellar.models.Table.get_table_name"

    # 使用 Tree-sitter 替换目标函数的代码
    replace_groundtruth_code_with_treesitter(codegraph, target_function)

    # 打印修改后的代码以验证
    for node_id, node_data in codegraph.nodes(data=True):
        if "code" in node_data:
            print(f"Node {node_data.get('label')} - Code:\n{node_data['code']}\n")
