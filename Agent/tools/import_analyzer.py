import os
import ast
import jedi
import logging

# Set up logging to help with debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Function to parse Python files and find import statements with their coordinates
def parse_and_resolve_imports(file_path):
    """
    使用 AST 解析给定 Python 文件中的所有导入语句，并使用 Jedi 查找定义。
    :param file_path: 要解析的 Python 文件路径
    :return: 导入语句及其定义的位置
    """
    with open(file_path, "r") as file:
        source_code = file.read()

    logger.debug("Source code loaded from %s", file_path)
    logger.debug("Source code length: %d", len(source_code))

    # Parse source code using Python's AST
    tree = ast.parse(source_code, filename=file_path)
    imports = []  # Using a list to collect unique import statements

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Handle import statements, e.g., import numpy or import numpy as np
            for alias in node.names:
                module_name = alias.name
                alias_name = alias.asname
                name = f"{module_name} as {alias_name}" if alias_name else module_name
                imports.append((name, alias.lineno, alias.col_offset))
                logger.debug("Found import: %s at line %d, column %d", name, alias.lineno, alias.col_offset)
        elif isinstance(node, ast.ImportFrom):
            # Handle from ... import ... statements
            module_name = node.module if node.module else ""
            for alias in node.names:
                imported_name = alias.name
                alias_name = alias.asname
                if imported_name == "*":
                    full_name = f"{module_name}.*"
                else:
                    full_name = f"{module_name}.{imported_name}" if module_name else imported_name
                if alias_name:
                    full_name = f"{full_name} as {alias_name}"
                imports.append((full_name, alias.lineno, alias.col_offset))
                logger.debug("Found import from: %s at line %d, column %d", full_name, alias.lineno, alias.col_offset)

    # Log the collected imports
    logger.debug("Collected imports: %s", imports)

    # Resolve imports using Jedi after collecting all imports
    for name, line, column in imports:
        definition_path, code_snippet, docstring = resolve_import_with_jedi(file_path, line, column)
        print(f"导入模块: {name}, 位于行: {line}, 列: {column}")
        if definition_path:
            print(f"定义位置: {definition_path}\n代码片段:\n{code_snippet}\n")
            if docstring:
                print(f"文档字符串:\n{docstring}\n")
        else:
            print("未找到定义位置或已忽略。")

# Function to find definitions using Jedi
def resolve_import_with_jedi(file_path, line, column):
    script = jedi.Script(path=file_path)
    definitions = script.goto(line=line, column=column, follow_imports=True, follow_builtin_imports=True)
    if definitions:
        for definition in definitions:
            if definition.module_path:
                docstring = definition.docstring(raw=True) if definition.docstring() else None
                if definition.type == "module":
                    # If the definition is a module, return the entire module path
                    with open(definition.module_path, "r") as f:
                        code_snippet = f.read()
                    return definition.module_path, code_snippet, docstring
                else:
                    # If the definition is not a module, return the specific code snippet
                    start_pos = definition.get_definition_start_position()
                    end_pos = definition.get_definition_end_position()
                    if start_pos and end_pos:
                        with open(definition.module_path, "r") as f:
                            lines = f.readlines()
                            code_snippet = "\n".join(lines[start_pos[0] - 1:end_pos[0]]).strip()
                    else:
                        code_snippet = ""
                    return definition.module_path, code_snippet, docstring
    return None, None, None

# Main function to parse a directory and resolve imports
if __name__ == "__main__":
    project_root_path = "/home/shixianjie/codegraph/codegraph/example_repo"
    target_file_path = "/home/shixianjie/codegraph/codegraph/example_repo/module_a/a.py"
    parse_and_resolve_imports(target_file_path)
