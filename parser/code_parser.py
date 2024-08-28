import ast
import os

class CodeParser:
    def __init__(self, project_path):
        self.project_path = project_path
        self.files = []
        self.classes = {}
        self.functions = {}
        self.calls = []

    def parse(self):
        py_files = self._get_py_files()
        for file in py_files:
            self._parse_file(file)

    def _get_py_files(self):
        py_files = []
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
        return py_files

    def _add_parents(self, node, parent=None):
        for child in ast.iter_child_nodes(node):
            child.parent = node
            self._add_parents(child, node)

    def _parse_file(self, file_path):
        with open(file_path, "r") as file:
            file_content = file.read()
        tree = ast.parse(file_content)

        self._add_parents(tree)

        current_file = file_path
        self.files.append(current_file)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = f"{current_file}.{node.name}"
                self.classes[class_name] = {"file": current_file, "methods": []}
                for subnode in node.body:
                    if isinstance(subnode, ast.FunctionDef):
                        func_name = f"{class_name}.{subnode.name}"
                        self.functions[func_name] = {"file": current_file}
                        self.classes[class_name]["methods"].append(func_name)
            elif isinstance(node, ast.FunctionDef):
                # 仅处理直接定义在模块或类中的函数
                if isinstance(node.parent, (ast.Module, ast.ClassDef)):
                    if isinstance(node.parent, ast.ClassDef):
                        func_name = f"{current_file}.{node.parent.name}.{node.name}"
                    else:
                        func_name = f"{current_file}.{node.name}"
                    # 确保函数名唯一
                    if func_name not in self.functions:
                        self.functions[func_name] = {"file": current_file}
            elif isinstance(node, ast.Call):
                caller_func = self._get_current_function(node)
                callee_func = self._get_called_function(node)
                if caller_func and callee_func:
                    self.calls.append((caller_func, callee_func))

    def _get_current_function(self, node):
        while node:
            if isinstance(node, ast.FunctionDef):
                if isinstance(node.parent, ast.ClassDef):
                    return f"{self.files[-1]}.{node.parent.name}.{node.name}"
                return f"{self.files[-1]}.{node.name}"
            node = getattr(node, "parent", None)
        return None

    def _get_called_function(self, node):
        if isinstance(node.func, ast.Name):
            return f"{self.files[-1]}.{node.func.id}"
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{self.files[-1]}.{node.func.value.id}.{node.func.attr}"
            return f"{self.files[-1]}.{node.func.attr}"
        return None
