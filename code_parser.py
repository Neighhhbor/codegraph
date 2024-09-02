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

class CodeParser:
    def __init__(self, project_path, repo_name):
        self.project_path = project_path
        self.repo_name = repo_name
        self.parser = self._init_parser()
        self.trees = {}  # 存储每个文件的树结构
        self.calls = []  # 存储调用关系
        self.imports = {}  # 存储import关系

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

            elif child.type == 'call':
                # 处理函数调用，记录调用关系
                caller_name = parent_node.fullname  # 调用者是当前节点的父节点
                callee_name = self._get_called_function(child, file_path, caller_name)
                if callee_name:
                    self.calls.append((caller_name, callee_name))

            elif child.type == 'import_statement':
                # 处理import关系，记录import的模块
                for name_node in child.named_children:
                    if name_node.type == 'dotted_name' or name_node.type == 'identifier':
                        import_name = self._get_node_text(name_node, file_path)
                        as_name = import_name  # 默认使用原名，如果有别名会在下面处理
                    if name_node.type == 'alias':
                        as_name = self._get_node_text(name_node.child_by_field_name('name'), file_path)
                        import_name = self._get_node_text(name_node.child_by_field_name('asname'), file_path)
                    self.imports[as_name] = import_name

            elif child.type == 'import_from_statement':
                # 处理from ... import ...形式的导入
                module_name_node = child.child_by_field_name('module')
                module_name = self._get_node_text(module_name_node, file_path) if module_name_node else None

                for import_node in child.named_children:
                    if import_node.type == 'import_clause':
                        import_name = self._get_node_text(import_node.child_by_field_name('name'), file_path)
                        as_name = import_name  # 默认使用原名，如果有别名会在下面处理
                        if import_node.child_by_field_name('alias'):
                            as_name = self._get_node_text(import_node.child_by_field_name('alias'), file_path)
                        if module_name:
                            self.imports[as_name] = f"{module_name}.{import_name}"
                        else:
                            self.imports[as_name] = import_name

            else:
                # 递归处理其他子节点
                self._extract_items(child, file_path, parent_node)

    def _get_called_function(self, node, file_path, caller_fullname):
        func_node = node.child_by_field_name('function')
        if not func_node:
            return None

        # 拼接被调用函数的名字
        parts = []
        while func_node:
            if func_node.type in ('identifier', 'attribute'):
                parts.insert(0, self._get_node_text(func_node, file_path))
            func_node = func_node.child_by_field_name('value')

        callee_name = ".".join(parts)

        # 优先通过import查找被调用函数
        first_part = callee_name.split(".")[0]
        if first_part in self.imports:
            callee_name = callee_name.replace(first_part, self.imports[first_part], 1)
            return callee_name

        # 如果import中没有匹配项，则返回假定的全名
        if "." in callee_name:
            context_parts = callee_name.split(".")
            callee_fullname = ".".join([caller_fullname.rsplit(".", len(context_parts) - 1)[0]] + context_parts)
        else:
            callee_fullname = f"{caller_fullname.rsplit('.', 1)[0]}.{callee_name}"

        return callee_fullname

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
