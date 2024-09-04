import tree_sitter_python as tspython
from tree_sitter import Language, Parser
import os

class Node:
    def __init__(self, name, node_type, code=None, signature=None, parent_fullname=None):
        self.name = name
        self.node_type = node_type  # 'directory', 'module', 'class', 'function'
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
        self.root = Node(repo_name, 'directory')  # 项目的根节点
        self.nodes = {repo_name: self.root}  # 存储所有创建的节点
        self.defined_symbols = {}  # 用于存储函数和类的定义，key为name，value为定义路径列表

    def _init_parser(self):
        PY_LANGUAGE = Language(tspython.language())
        parser = Parser(PY_LANGUAGE)
        return parser

    def parse(self):
        self._build_tree(self.project_path, self.root)

    def _build_tree(self, current_path, parent_node):
        for item in os.listdir(current_path):
            item_path = os.path.join(current_path, item)
            if os.path.isdir(item_path):
                # 创建目录节点
                dir_node = self._create_node(item, 'directory', parent_node)
                # 递归遍历子目录
                self._build_tree(item_path, dir_node)
            elif item.endswith(".py"):
                # 创建文件模块节点并解析
                module_node = self._create_node(item, 'module', parent_node)
                self._parse_file(item_path, module_node)

    def _create_node(self, name, node_type, parent_node):
        # 去掉文件扩展名（仅对模块节点）
        if node_type == 'module' and name.endswith('.py'):
            name = name[:-3]  # 去除 .py 后缀

        # 生成全名
        if parent_node.fullname:
            full_name = f"{parent_node.fullname}.{name}"
        else:
            full_name = name

        # 创建节点
        node = Node(name, node_type, parent_fullname=parent_node.fullname)
        parent_node.add_child(node)
        self.nodes[full_name] = node

        return node

    def _parse_file(self, file_path, module_node):
        with open(file_path, "r") as file:
            file_content = file.read()

        tree = self.parser.parse(bytes(file_content, "utf8"))

        # 递归构建文件内的树形结构
        self._extract_items(tree.root_node, file_path, module_node)

    def _extract_items(self, node, file_path, parent_node):
        for child in node.children:
            if child.type == 'class_definition':
                class_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                class_signature = self._get_node_text(child, file_path)
                class_node = Node(class_name, 'class', self._get_code_segment(child, file_path), class_signature, parent_node.fullname)
                parent_node.add_child(class_node)

                # 注册类到 defined_symbols
                self._register_symbol(class_name, class_node.fullname)

                # 递归处理子节点
                self._extract_items(child, file_path, class_node)

            elif child.type == 'function_definition':
                func_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                func_signature = self._get_node_text(child, file_path)
                func_node = Node(func_name, 'function', self._get_code_segment(child, file_path), func_signature, parent_node.fullname)
                parent_node.add_child(func_node)

                # 注册函数到 defined_symbols
                self._register_symbol(func_name, func_node.fullname)

                # 递归处理子节点
                self._extract_items(child, file_path, func_node)

            else:
                # 递归处理其他子节点
                self._extract_items(child, file_path, parent_node)

    def _register_symbol(self, name, fullname):
        """
        注册函数或类的定义到 defined_symbols 字典中。
        如果符号已经存在，添加到其定义路径列表中。
        """
        if name in self.defined_symbols:
            self.defined_symbols[name].append(fullname)
        else:
            self.defined_symbols[name] = [fullname]

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
