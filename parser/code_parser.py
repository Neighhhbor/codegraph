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
                class_name = self._get_node_text(child.children[1], file_path)
                class_full_name = f"{file_path}.{class_name}"
                self.classes[class_full_name] = {"file": file_path, "methods": []}
                
                # 遍历该类的内容，父节点设为当前类
                self._extract_items(child, file_path, class_full_name)

            elif child.type == 'function_definition':
                func_name = self._get_node_text(child.children[1], file_path)
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
        while node:
            if node.type == 'function_definition':
                if node.parent.type == 'class_definition':
                    return f"{self.files[-1]}.{self._get_node_text(node.parent.children[1], self.files[-1])}.{self._get_node_text(node.children[1], self.files[-1])}"
                return f"{self.files[-1]}.{self._get_node_text(node.children[1], self.files[-1])}"
            node = node.parent
        return None

    def _get_called_function(self, node):
        func_node = node.child_by_field_name('function')
        if func_node.type == 'identifier':
            return f"{self.files[-1]}.{self._get_node_text(func_node, self.files[-1])}"
        elif func_node.type == 'attribute':
            value_node = func_node.child_by_field_name('value')
            if value_node.type == 'identifier':
                possible_class = f"{self.files[-1]}.{self._get_node_text(value_node, self.files[-1])}"
                for func in self.functions:
                    if func.startswith(possible_class):
                        return f"{possible_class}.{self._get_node_text(func_node.child_by_field_name('attribute'), self.files[-1])}"
            return f"{self.files[-1]}.{self._get_node_text(func_node.child_by_field_name('attribute'), self.files[-1])}"
        return None
