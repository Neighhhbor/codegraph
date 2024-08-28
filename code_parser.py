import tree_sitter_python as tspython
from tree_sitter import Language, Parser
import os

class CodeParser:
    def __init__(self, project_path):
        self.project_path = project_path
        self.parser = self._init_parser()
        self.files = []
        self.classes = {}
        self.functions = {}
        self.calls = []

    def _init_parser(self):
        language = Language(tspython.language(), 'python')
        parser = Parser()
        parser.set_language(language)
        return parser

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

    def _parse_file(self, file_path):
        with open(file_path, "r") as file:
            file_content = file.read()

        tree = self.parser.parse(bytes(file_content, "utf8"))
        self.files.append(file_path)

        self._extract_items(tree.root_node, file_path, None)

    def _extract_items(self, node, file_path, parent):
        for child in node.children:
            if child.type == 'class_definition':
                class_name_node = child.child_by_field_name('name')
                class_name = self._get_node_text(class_name_node, file_path)
                class_full_name = f"{file_path}.{class_name}"
                self.classes[class_full_name] = {"file": file_path, "methods": []}
                
                self._extract_items(child, file_path, class_full_name)

            elif child.type == 'function_definition':
                func_name_node = child.child_by_field_name('name')
                func_name = self._get_node_text(func_name_node, file_path)
                if parent and parent in self.classes:
                    func_full_name = f"{parent}.{func_name}"
                    self.functions[func_full_name] = {"file": file_path, "class": parent}
                    self.classes[parent]["methods"].append(func_full_name)
                else:
                    func_full_name = f"{file_path}.{func_name}"
                    if not any(func_full_name.endswith(f".{func_name}") for func_full_name in self.functions):
                        self.functions[func_full_name] = {"file": file_path}
                
            elif child.type == 'call':
                caller_func = self._get_current_function(node)
                callee_func = self._get_called_function(child)
                if caller_func and callee_func:
                    self.calls.append((caller_func, callee_func))

            self._extract_items(child, file_path, parent)

    def _get_node_text(self, node, file_path):
        start_byte = node.start_byte
        end_byte = node.end_byte
        with open(file_path, "r") as file:
            file_content = file.read()
        return file_content[start_byte:end_byte]

    def _get_current_function(self, node):
        parts = []
        while node:
            if node.type == 'function_definition':
                parts.insert(0, self._get_node_text(node.child_by_field_name('name'), self.files[-1]))
            elif node.type == 'class_definition':
                parts.insert(0, self._get_node_text(node.child_by_field_name('name'), self.files[-1]))
            node = node.parent
        if parts:
            full_name = f"{self.files[-1]}." + ".".join(parts)
            print(f"当前函数的完整链路: {full_name}")
            return full_name
        print("无法解析当前函数")
        return None

    def _get_called_function(self, node):
        func_node = node.child_by_field_name('function')
        if not func_node:
            print(f"无法找到被调用函数: {node}")
            return None

        parts = []
        while func_node:
            if func_node.type in ('identifier', 'attribute'):
                parts.insert(0, self._get_node_text(func_node, self.files[-1]))
            func_node = func_node.child_by_field_name('value')

        full_name = ".".join(parts)
        for func in self.functions:
            if func.endswith(full_name):
                print(f"被调用函数的完整链路: {func}")
                return func

        print(f"无法找到被调用函数: {node}")
        return full_name


    def _get_imports(self):
        imports = []
        for file in self.files:
            with open(file, "r") as f:
                content = f.read()
                tree = self.parser.parse(bytes(content, "utf8"))
                for node in tree.root_node.children:
                    if node.type == "import_statement":
                        module_name = self._get_node_text(node.child_by_field_name('name'), file)
                        imports.append(module_name)
                    elif node.type == "import_from_statement":
                        module_name = self._get_node_text(node.child_by_field_name('module_name'), file)
                        imports.append(module_name)
        return imports
