import os
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
from lsp_client import LspClientWrapper
import logging

class CallAndImportParser:
    def __init__(self, project_path, repo_name):
        self.project_path = project_path
        self.repo_name = repo_name
        self.parser = self._init_parser()
        self.calls = []  # 存储调用关系
        self.imports = {}  # 存储import关系
        self.lsp_client = LspClientWrapper(project_root=project_path)
        self.logger = self._init_logger()
        self.trees = {}  # 存储每个文件的树形结构

    def _init_parser(self):
        language = Language(tspython.language(), 'python')
        parser = Parser()
        parser.set_language(language)
        return parser

    def _init_logger(self):
        logger = logging.getLogger('call_import_parser')
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)  # 设置为DEBUG模式
        return logger

    def parse(self):
        py_files = self._get_py_files()
        for file in py_files:
            self.logger.debug(f"Parsing file: {file}")
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

        # 构建模块名称
        module_name = self._get_module_name(file_path)

        self.logger.debug(f"Module name: {module_name}")

        # 保存当前文件的语法树
        self.trees[module_name] = tree.root_node

        # 递归分析import和调用关系
        self._extract_items(tree.root_node, file_path, module_name)

    def _get_module_name(self, file_path):
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _extract_items(self, node, file_path, current_fullname):
        for child in node.children:
            if child.type == 'class_definition' or child.type == 'function_definition':
                definition_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                full_definition_name = f"{current_fullname}.{definition_name}"
                self.logger.debug(f"Extracting {child.type} - {full_definition_name}")

                # 递归处理类或函数的子节点
                self._extract_items(child, file_path, full_definition_name)

            elif child.type == 'call':
                # 处理函数调用，记录调用关系
                callee_name = self._resolve_callee_name(child, file_path, current_fullname)
                if callee_name:
                    caller_name = current_fullname  # 调用者是当前所在的函数或类
                    self.logger.debug(f"Call statement: {self._get_node_text(child, file_path)}")
                    self.logger.debug(f"Static analysis Caller: {caller_name}")
                    self.logger.debug(f"Static analysis Callee: {callee_name}")

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
                self.logger.debug(f"Imports: {self.imports}")

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
                self.logger.debug(f"Imports from statement: {self.imports}")

            else:
                # 递归处理其他子节点
                self._extract_items(child, file_path, current_fullname)

    def _resolve_callee_name(self, node, file_path, current_fullname):
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
        self.logger.debug(f"Trying to resolve callee: {callee_name} in {file_path}")

        # 使用 LSP 的 request_definition 查找定义
        definition = self.lsp_client.find_definition(file_path, node.start_point[0], node.start_point[1])

        self.logger.debug(f"LSP definition result: {definition}")

        if isinstance(definition, list) and len(definition) > 0:
            definition = definition[0]  # 如果是列表，取第一个元素
        else:
            self.logger.debug(f"Definition list is empty or not a list: {definition}")
            return None

        callee_fullname = self._convert_definition_to_fullname(definition)
        self.logger.debug(f"Resolved callee full name: {callee_fullname}")
        return callee_fullname

    def _convert_definition_to_fullname(self, definition):
        # 将定义的位置转换为模块名称和函数名称的完整路径
        self.logger.debug(f"Converting definition to full name: {definition}")
        file_path = definition['absolutePath']  # 使用绝对路径
        module_name = self._get_module_name(file_path)
        function_name = f"{module_name}.L{definition['range']['start']['line']}_C{definition['range']['start']['character']}"
        return function_name

    def _get_node_text(self, node, file_path):
        if node is None:
            return ""
        start_byte = node.start_byte
        end_byte = node.end_byte
        with open(file_path, "r") as file:
            file_content = file.read()
        return file_content[start_byte:end_byte]

    def _find_function_by_line(self, module_name, line):
        """
        根据模块名和行号查找函数的完整名
        """
        if module_name in self.trees:
            return self._find_in_tree(self.trees[module_name], line)
        return None

    def _find_in_tree(self, node, line):
        """
        在语法树中递归查找对应行号的函数
        """
        for child in node.children:
            if 'function' in child.node_type and self._node_covers_line(child, line):
                return child.fullname
            result = self._find_in_tree(child, line)
            if result:
                return result
        return None

    def _node_covers_line(self, node, line):
        """
        检查节点是否覆盖给定的行号
        """
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        return start_line <= line <= end_line
