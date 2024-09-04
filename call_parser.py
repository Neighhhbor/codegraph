import os
from tree_sitter import Parser, Language
import tree_sitter_python as tspython
from lsp_client import LspClientWrapper
import logging

class CallParser:
    def __init__(self, project_path, repo_name, code_graph, defined_symbols):
        self.project_path = project_path
        self.repo_name = repo_name
        self.code_graph = code_graph
        self.defined_symbols = defined_symbols  # 从 ContainsParser 获取的符号定义
        self.calls = []  # 存储调用关系 (caller, callee)

        # 配置日志记录
        self.logger = logging.getLogger('call_parser')
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger.addHandler(handler)

        # 初始化LSP客户端
        self.lsp_client = LspClientWrapper(self.project_path)
        self.parser = self._init_parser()

    def _init_parser(self):
        PY_LANGUAGE = Language(tspython.language())
        parser = Parser(PY_LANGUAGE)
        return parser

    def parse(self):
        """
        解析项目中的所有 Python 文件，构建函数调用关系。
        """
        py_files = self._get_py_files()
        for file in py_files:
            self._parse_file(file)

    def _get_py_files(self):
        """
        获取项目中所有的 Python 文件
        """
        py_files = []
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
        return py_files

    def _parse_file(self, file_path):
        with open(file_path, "r") as file:
            file_content = file.read()

        # 使用 tree-sitter 解析文件
        tree = self.parser.parse(bytes(file_content, "utf8"))

        # 构建模块名称
        module_name = self._get_module_name(file_path)

        # 递归分析调用关系
        self._extract_calls(tree.root_node, file_path, module_name)

    def _get_module_name(self, file_path):
        """根据文件路径生成模块全名"""
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _extract_calls(self, node, file_path, current_fullname):
        """
        递归分析文件中的函数调用关系，保持与 ContainsParser 一致的自顶向下路径
        """
        for child in node.children:
            if child.type == 'class_definition' or child.type == 'function_definition':
                # 处理类和函数，构建它们的完整路径
                name = self._get_node_text(child.child_by_field_name('name'), file_path)
                fullname = f"{current_fullname}.{name}"

                # 递归处理子节点
                self._extract_calls(child, file_path, fullname)

            elif child.type == 'call':
                # 处理函数调用
                func_name_node = child.child_by_field_name('function')
                if func_name_node:
                    callee_name = self._get_node_text(func_name_node, file_path)
                    #分割线
                    self.logger.info("-" * 50)
                    self._handle_call(callee_name, current_fullname, file_path, func_name_node)
            else:
                # 递归处理其他节点
                self._extract_calls(child, file_path, current_fullname)

    def _handle_call(self, callee_name, caller_fullname, file_path, func_name_node):
        """
        处理全局函数和方法调用的统一逻辑
        """
        self.logger.info(f"Found call to {callee_name} in {caller_fullname}")

        if func_name_node.type == 'attribute':
            # 处理类方法或实例方法调用
            object_node = func_name_node.child_by_field_name('object')
            method_node = func_name_node.child_by_field_name('attribute')

            object_name = self._get_node_text(object_node, file_path) if object_node else None
            method_name = self._get_node_text(method_node, file_path) if method_node else None

            self.logger.info(f"Found method call: {object_name}.{method_name} in {caller_fullname}")
            self._process_method_call(object_name, method_name, caller_fullname)

        else:
            # 处理全局函数调用
            self._process_function_call(callee_name, caller_fullname, file_path, func_name_node)

    def _process_function_call(self, callee_name, caller_fullname, file_path, func_name_node):
        """
        处理全局函数调用
        """
        if callee_name in self.defined_symbols:
            definition_paths = self.defined_symbols[callee_name]
            if len(definition_paths) == 1:
                # 唯一定义，直接使用
                callee_fullname = definition_paths[0]
                self.calls.append((caller_fullname, callee_fullname))
                self.logger.info(f"Recorded function call: {caller_fullname} -> {callee_fullname}")
            else:
                # 多个定义路径，使用 LSP 确定具体定义
                definition = self.lsp_client.find_definition(file_path, func_name_node.start_point[0], func_name_node.start_point[1])
                self._resolve_call_with_lsp(caller_fullname, definition, definition_paths, callee_name)
        else:
            self.logger.info(f"Call to external function {callee_name} in {caller_fullname}, skipping.")

    def _process_method_call(self, object_name, method_name, caller_fullname):
        """
        处理类方法或实例方法调用
        """
        if object_name in self.defined_symbols:
            class_definitions = self.defined_symbols[object_name]
            if len(class_definitions) == 1:
                # 静态方法调用，记录类方法调用
                callee_fullname = f"{class_definitions[0]}.{method_name}"
                self.calls.append((caller_fullname, callee_fullname))
                self.logger.info(f"Recorded static method call: {caller_fullname} -> {callee_fullname}")
            else:
                self.logger.warning(f"Multiple class definitions for {object_name}, skipping method call.")
        else:
            if method_name in self.defined_symbols:
                method_definitions = self.defined_symbols[method_name]
                if len(method_definitions) == 1:
                    callee_fullname = method_definitions[0]
                    self.calls.append((caller_fullname, callee_fullname))
                    self.logger.info(f"Recorded instance method call: {caller_fullname} -> {callee_fullname}")
                else:
                    self.logger.warning(f"Multiple method definitions for {method_name}, skipping.")
            else:
                self.logger.info(f"Method {method_name} not found for object {object_name}, skipping.")

    def _resolve_call_with_lsp(self, caller_fullname, definition, definition_paths, callee_name):
        """
        使用 LSP 来确定调用函数的位置
        """
        if definition:
            callee_fullname = self._get_fullname_from_definition(definition)
            if callee_fullname and any(callee_fullname.startswith(path) for path in definition_paths):
                self.calls.append((caller_fullname, callee_fullname))
                self.logger.info(f"Recorded call: {caller_fullname} -> {callee_fullname}")
            else:
                self.logger.warning(f"Could not determine the correct definition for {callee_name} called in {caller_fullname}")

    def _get_fullname_from_definition(self, definition):
        """
        从 LSP 的定义响应中提取完整的函数路径
        """
        if not isinstance(definition, list) or len(definition) == 0:
            self.logger.error(f"Unexpected definition format or empty list: {definition}")
            return None

        # 取列表中的第一个元素
        definition = definition[0]

        if not isinstance(definition, dict):
            self.logger.error(f"Unexpected definition format: {definition}")
            return None

        # 根据LSP返回的定义位置，计算被调用函数的全名
        def_file_path = os.path.abspath(definition['uri'].replace('file://', ''))
        line = definition['range']['start']['line']
        
        # 解析被调用函数所在模块
        module_name = self._get_module_name(def_file_path)

        # 根据行号反向推断函数的全名
        func_fullname = f"{module_name}"
        return func_fullname

    def _get_node_text(self, node, file_path):
        """
        提取 AST 节点对应的源代码文本，使用行列号而非字节
        """
        if node is None:
            return ""

        start_line, start_column = node.start_point
        end_line, end_column = node.end_point

        with open(file_path, "r") as file:
            file_lines = file.readlines()

        if start_line == end_line:
            # 同一行的情况，直接从 start_column 到 end_column
            return file_lines[start_line][start_column:end_column].strip()
        else:
            # 跨多行的情况，处理起始行、中间行和结束行
            extracted_text = []
            extracted_text.append(file_lines[start_line][start_column:].strip())
            for line in range(start_line + 1, end_line):
                extracted_text.append(file_lines[line].strip())
            extracted_text.append(file_lines[end_line][:end_column].strip())
            return " ".join(extracted_text)
