import tree_sitter_python as tspython
from tree_sitter import Language, Parser
import os

class Node:
    def __init__(self, name, node_type, code, signature=None, parent_fullname=None):
        self.name = name
        self.node_type = node_type  # 'module', 'class', 'function'
        self.children = []
        self.code = code
        self.signature = signature

        # 生成全名：从根节点到当前节点的路径名
        if parent_fullname:
            self.fullname = f"{parent_fullname}.{name}"
        else:
            self.fullname = name

    def add_child(self, child_node):
        self.children.append(child_node)

class ContainsParser:
    def __init__(self, project_path, repo_name):
        self.project_path = project_path
        self.repo_name = repo_name
        self.parser = self._init_parser()
        self.trees = {}  # 存储每个文件的树结构

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

        # 构建模块节点
        module_name = self._get_module_name(file_path)
        module_node = Node(module_name, 'module', file_content)

        # 递归构建树形结构
        self._extract_items(tree.root_node, file_path, module_node)

        # 保存树形结构
        self.trees[file_path] = module_node

    def _get_module_name(self, file_path):
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _extract_items(self, node, file_path, parent_node):
        for child in node.children:
            if child.type == 'class_definition':
                class_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                class_signature = self._get_node_text(child, file_path)
                class_node = Node(class_name, 'class', self._get_code_segment(child, file_path), class_signature, parent_node.fullname)
                parent_node.add_child(class_node)
                # 递归处理子节点
                self._extract_items(child, file_path, class_node)

            elif child.type == 'function_definition':
                func_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                func_signature = self._get_node_text(child, file_path)
                func_node = Node(func_name, 'function', self._get_code_segment(child, file_path), func_signature, parent_node.fullname)
                parent_node.add_child(func_node)
                # 递归处理子节点
                self._extract_items(child, file_path, func_node)

            else:
                # 递归处理其他子节点
                self._extract_items(child, file_path, parent_node)

    def _get_node_text(self, node, file_path):
        if node is None:
            return ""
        start_byte = node.start_byte
        end_byte = node.end_byte
        with open(file_path, "r") as file:
            file_content = file.read()
        return file_content[start_byte:end_byte]

    def _get_code_segment(self, node, file_path):
        return self._get_node_text(node, file_path)
