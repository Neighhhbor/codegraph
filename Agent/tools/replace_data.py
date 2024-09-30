import os
import networkx as nx
from tree_sitter import Parser, Language
import tree_sitter_python as tspython
import json
import re
from typing import List, Dict, Any


# 使用 Tree-sitter 解析代码
def parse_code_with_treesitter(code):
    """使用 Tree-sitter 解析 Python 代码"""
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser()
    parser.language = PY_LANGUAGE
    tree = parser.parse(bytes(code, "utf8"))
    return tree

def get_involved_names(node_label: str, codegraph) -> Dict[str, str]:
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

def replace_function_body(tree, code, target_function_name):
    """
    只替换目标函数体（block），不影响其他函数。
    :param tree: Tree-sitter 解析后的语法树
    :param code: 原始 Python 代码字符串
    :param target_function_name: 需要替换函数体的目标函数名
    :return: 替换后的代码
    """
    cursor = tree.walk()  # 获取 AST 游标
    updated_code = code

    def visit_node(cursor):
        nonlocal updated_code

        # 如果节点是 'function_definition'
        if cursor.node.type == 'function_definition':
            function_id = cursor.node.child_by_field_name('name')
            function_name = function_id.text.decode('utf-8')

            # 仅替换目标函数的代码
            if function_name == target_function_name:
                # 找到函数体并替换
                body_node = cursor.node.child_by_field_name('body')
                if body_node:
                    body_start_byte = body_node.start_byte
                    body_end_byte = cursor.node.end_byte
                    new_body = "<CODETOCOMPLETE>"

                    # 更新代码：替换函数体
                    updated_code = updated_code[:body_start_byte] + new_body + updated_code[body_end_byte:]

        # 递归处理子节点
        if cursor.goto_first_child():
            visit_node(cursor)
            cursor.goto_parent()  # 返回父节点

        # 递归处理兄弟节点
        while cursor.goto_next_sibling():
            visit_node(cursor)

    visit_node(cursor)  # 从根节点开始遍历

    return updated_code


def replace_code_in_node(node_id, node_data, function_name):
    """在节点中替换目标函数体"""
    if "code" in node_data:
        code = node_data["code"]
        tree = parse_code_with_treesitter(code)  # 首先解析代码

        # 遍历 AST 并找到要替换的函数体
        updated_code = replace_function_body(tree, code, function_name)

        if updated_code != code:
            node_data["code"] = updated_code
            return node_id
    return None


def replace_groundtruth_code_with_treesitter(codegraph: nx.DiGraph, target_function: str):
    """
    使用 Tree-sitter 替换目标函数、类和模块节点中的代码，将其函数体替换为 <CODETOCOMPLETE>。
    
    :param codegraph: NetworkX 图对象，包含代码节点
    :param target_function: 待补全的目标函数名称（如 'stellar.stellar.models.Table.get_table_name'）
    :return: 返回被修改的节点
    """
    modified_nodes = set()

    # 获取目标函数、类、模块的相关节点
    involved_names = get_involved_names(target_function, codegraph)

    # 替换函数节点代码
    if 'function' in involved_names:
        function_name = involved_names['function'].split('.')[-1]  # 获取函数名
        modified_node = replace_code_in_node(involved_names['function'], codegraph.nodes[involved_names['function']], function_name)
        if modified_node:
            modified_nodes.add(modified_node)

    # 替换类节点中的目标函数
    if 'class' in involved_names:
        modified_node = replace_code_in_node(involved_names['class'], codegraph.nodes[involved_names['class']], function_name)
        if modified_node:
            modified_nodes.add(modified_node)

    # 替换模块节点中的目标类
    if 'module' in involved_names:
        modified_node = replace_code_in_node(involved_names['module'], codegraph.nodes[involved_names['module']], function_name)
        if modified_node:
            modified_nodes.add(modified_node)

    return modified_nodes



# 加载 JSON 格式的 NetworkX 图
def load_json_graph(path: str) -> nx.DiGraph:
    """加载 JSON 文件并将其转换为 NetworkX DiGraph"""
    with open(path, 'r') as f:
        data = json.load(f)
    graph = nx.node_link_graph(data)  # 使用 node-link 格式读取图
    return graph


# 保存修改后的图为 JSON 文件
def save_json_graph(graph: nx.DiGraph, path: str):
    """将修改后的 NetworkX DiGraph 导出为 JSON 文件"""
    graph_data = nx.node_link_data(graph)  # 将图转换为 node-link 格式
    with open(path, 'w') as f:
        json.dump(graph_data, f, indent=4)


if __name__ == "__main__":
    # 示例：在目标节点中替换代码
    json_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs/stellar.json"
    codegraph = load_json_graph(json_path)

    # 定义目标函数的名称
    target_function = "stellar.stellar.models.Table.get_table_name"

    # 使用 Tree-sitter 替换目标函数的代码
    modified_nodes = replace_groundtruth_code_with_treesitter(codegraph, target_function)

    # 打印修改后的代码以验证
    print("Modified Nodes:")
    for node_id in modified_nodes:
        node_data = codegraph.nodes[node_id]
        if "code" in node_data:
            print(f"Node {node_id} - Code:\n{node_data['code']}\n")

    # 保存修改后的图为新的 JSON 文件
    save_json_graph(codegraph, "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs/stellar_modified.json")
