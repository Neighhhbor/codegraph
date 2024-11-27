import os
import re
import sys
from typing import List, Dict, Optional, Tuple

def parse_imports(file_path: str) -> List[Tuple[str, str]]:
    """
    解析Python文件中的所有导入语句
    返回一个列表，每个元素是一个元组 (导入语句, 模块名)
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 匹配导入语句的正则表达式
    pattern = r'(?:from\s+(\.{0,2}\S+)\s+import\s+\S+|import\s+(\S+))'
    matches = re.findall(pattern, content)

    imports = []
    for match in matches:
        if match[0]:  # from ... import ...
            imports.append(('from', match[0]))
        else:  # import ...
            imports.append(('import', match[1]))

    return imports

def resolve_import(import_type: str, module: str, file_path: str) -> Optional[str]:
    """
    解析导入语句，返回对应的文件路径
    """
    base_dir = os.path.dirname(file_path)
    
    if import_type == 'from' and module.startswith('.'):
        # 处理相对导入
        level = module.count('.')
        module = module.lstrip('.')
        parts = module.split('.')
        resolved_path = os.path.normpath(os.path.join(base_dir, *([os.pardir] * (level - 1)), *parts))
    else:
        # 处理绝对导入
        parts = module.split('.')
        resolved_path = os.path.join(base_dir, *parts)

    # 检查是否为包或模块
    if os.path.isdir(resolved_path):
        init_file = os.path.join(resolved_path, '__init__.py')
        if os.path.exists(init_file):
            return init_file
    elif os.path.exists(resolved_path + '.py'):
        return resolved_path + '.py'

    return None

def get_import_contents(file_path: str) -> Dict[str, str]:
    """
    获取Python文件中所有导入的文件内容
    返回一个字典，键是导入语句，值是对应文件的内容
    """
    imports = parse_imports(file_path)
    import_contents = {}

    for import_type, module in imports:
        resolved_path = resolve_import(import_type, module, file_path)
        if resolved_path:
            try:
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 如果文件太大，只返回前1000个字符
                    import_contents[f"{import_type} {module}"] = content[:1000] + "..." if len(content) > 1000 else content
            except Exception as e:
                import_contents[f"{import_type} {module}"] = f"读取文件时出错: {str(e)}"
        else:
            import_contents[f"{import_type} {module}"] = f"无法解析导入: {module}"

    return import_contents

def get_third_party_imports(file_path: str) -> List[str]:
    """
    获取Python文件中的第三方库导入
    """
    imports = parse_imports(file_path)
    third_party_imports = []
    standard_libs = set(['os', 'sys', 're', 'datetime'])  # 这里可以添加更多标准库

    for import_type, module in imports:
        top_level_module = module.split('.')[0]
        if top_level_module not in standard_libs and not module.startswith('.'):
            third_party_imports.append(top_level_module)

    return list(set(third_party_imports))

def test_example_repo():
    repo_path = "/home/shixianjie/codegraph/codegraph/example_repo"  # 请替换为实际的仓库路径
    files_to_test = [
        os.path.join(repo_path, "main.py"),
        os.path.join(repo_path, "module_a", "a.py"),
        os.path.join(repo_path, "module_b", "b.py"),
        os.path.join(repo_path, "utils", "helper.py")
    ]

    for file_path in files_to_test:
        print(f"\n分析文件: {file_path}")
        
        print("导入内容:")
        import_contents = get_import_contents(file_path)
        for import_stmt, content in import_contents.items():
            print(f"  导入语句: {import_stmt}")
            print(f"  文件内容: {content[:100]}..." if len(content) > 100 else content)
        
        print("\n第三方库导入:")
        third_party_imports = get_third_party_imports(file_path)
        for lib in third_party_imports:
            print(f"  {lib}")

if __name__ == "__main__":
    test_example_repo()
