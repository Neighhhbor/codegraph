import ast
import jedi
import os
import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python as tsp


# 初始化 Tree-sitter 解析器
PYTHON_LANGUAGE = Language(tsp.language())

parser = Parser()
parser.language = (PYTHON_LANGUAGE)



def parse_import_statements_with_treesitter(file_path):
    """
    使用 Tree-sitter 解析给定 Python 文件中的所有导入语句，并返回它们的位置。
    :param file_path: 要解析的 Python 文件路径
    :return: 导入语句列表，每项包含模块名、行号和列号，以及导入符号的起始和结束位置
    """
    with open(file_path, "r") as file:
        source_code = file.read()

    tree = parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node

    imports = []

    def traverse(node):
        if node.type == "import_statement":
            # 处理直接导入语句，例如 import numpy as np
            alias_name = None
            module_name = None
            for child in node.children:
                if child.type == "dotted_name":
                    module_name = source_code[child.start_byte:child.end_byte]
                elif child.type == "alias":
                    alias_name = source_code[child.child_by_field_name("name").start_byte:child.child_by_field_name("name").end_byte]
            if module_name:
                name = f"{module_name} as {alias_name}" if alias_name else module_name
                imports.append((name, node.start_point[0] + 1, node.start_point[1], node.end_point[0] + 1, node.end_point[1]))
        elif node.type == "import_from_statement":
            # 处理 from ... import ... 语句
            module_name = ""
            module_node = node.child_by_field_name("module")
            if module_node:
                module_name = source_code[module_node.start_byte:module_node.end_byte]
            
            for child in node.children:
                if child.type == "dotted_name" or child.type == "alias":
                    name = source_code[child.start_byte:child.end_byte]
                    full_name = f"{module_name}.{name}" if module_name else name
                    imports.append((full_name, child.start_point[0] + 1, child.start_point[1], child.end_point[0] + 1, child.end_point[1]))
        for child in node.children:
            traverse(child)

    traverse(root_node)
    return imports


def find_definition(file_path, module_name, line, column):
    """
    使用 Jedi 查找给定位置的符号定义。
    :param file_path: Python 文件路径
    :param module_name: 要查找的模块名
    :param line: 符号所在的行号
    :param column: 符号所在的列号
    :return: 符号定义的位置，包括文件路径和源代码片段
    """
    # 忽略第三方库和内置模块
    if module_name.startswith("numpy") or module_name.startswith("typing"):
        return None

    script = jedi.Script(path=file_path)
    definitions = script.goto(line=line, column=column, follow_imports=True, follow_builtin_imports=True)

    if definitions:
        # 尝试匹配符号名称以确保找到正确的定义
        for definition in definitions:
            if definition.full_name and module_name in definition.full_name:
                if definition.is_stub() or not definition.module_path:
                    continue
                
                definition_path = definition.module_path
                with open(definition_path, "r") as f:
                    source_code = f.read(500)  # 获取前 500 个字符的源代码片段
                return definition_path, source_code
    
    return None


def main(project_root, target_file):
    """
    主程序：
    - 解析给定 Python 文件中的导入语句
    - 查找每个导入的定义位置
    - 输出导入符号的部分源代码
    :param project_root: 项目根目录
    :param target_file: 要处理的 Python 文件路径
    """
    # 使用 Jedi 初始化项目上下文
    project = jedi.Project(path=project_root, smart_sys_path=True)
    imports = parse_import_statements_with_treesitter(target_file)

    print(f"解析到的导入语句 ({len(imports)} 个):\n")
    for module_name, line, col_start, line_end, col_end in imports:
        print(f"导入模块: {module_name}, 位于行: {line}, 列: {col_start}")
        # 使用精确的行和列位置来查找定义
        definition_info = find_definition(target_file, module_name, line, col_start)
        if definition_info:
            definition_path, source_code = definition_info
            print(f"定义位置: {definition_path}\n部分源代码:\n{source_code}\n")
        else:
            print("未找到定义位置或已忽略。")


if __name__ == "__main__":
    project_root_path = "/home/shixianjie/codegraph/codegraph/example_repo"
    target_file_path = "/home/shixianjie/codegraph/codegraph/example_repo/module_a/a.py"
    main(project_root_path, target_file_path)
