import os
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
from lsp_client import LspClientWrapper
import logging

class CallParser:
    def __init__(self, project_path, repo_name, code_graph):
        self.project_path = project_path
        self.repo_name = repo_name
        self.parser = self._init_parser()
        self.calls = []  # 存储调用关系 (caller, callee)
        self.lsp_client = LspClientWrapper(project_root=project_path)
        self.code_graph = code_graph  # 包含结构图

        # 配置日志记录
        self.logger = logging.getLogger('call_parser')
        self.logger.setLevel(logging.DEBUG)

    def _init_parser(self):
        language = Language(tspython.language(), 'python')
        parser = Parser()
        parser.set_language(language)
        return parser

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

        # 递归分析调用关系
        self._extract_calls(tree.root_node, file_path, module_name)

    def _get_module_name(self, file_path):
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _extract_calls(self, node, file_path, current_fullname, current_class=None):
        """
        遍历AST节点，查找所有的函数调用，并使用LSP解析被调用函数的定义位置。
        """
        for child in node.children:
            if child.type == 'class_definition':
                # 进入类定义，更新当前类的上下文
                class_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                class_fullname = f"{current_fullname}.{class_name}"
                self.logger.debug(f"Entering class: {class_fullname}")
                self._extract_calls(child, file_path, current_fullname, class_fullname)

            elif child.type == 'function_definition':
                # 进入一个函数定义，更新当前函数的上下文
                function_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                function_fullname = f"{current_class}.{function_name}" if current_class else f"{current_fullname}.{function_name}"
                self.logger.debug(f"Entering function: {function_fullname}")
                self._extract_calls(child, file_path, function_fullname, current_class)

            elif child.type == 'call':
                # 处理函数调用
                callee_name = self._resolve_callee_name(child, file_path)
                if callee_name:
                    self.calls.append((current_fullname, callee_name))
                    self.logger.debug(f"Added call: {current_fullname} -> {callee_name}")

            else:
                # 递归处理其他子节点
                self._extract_calls(child, file_path, current_fullname, current_class)

    def _resolve_callee_name(self, node, file_path):
        """
        使用LSP客户端解析被调用者的定义位置，并在已构建的图上查找目标节点。
        """
        func_node = node.child_by_field_name('function')
        if not func_node:
            return None

        # 获取被调用函数的名称
        callee_text = self._get_node_text(func_node, file_path)
        self.logger.debug(f"Resolved callee name from tree-sitter: {callee_text}")

        # 使用LSP客户端查找被调用函数的定义位置
        definition = self.lsp_client.find_definition(file_path, func_node.start_point[0], func_node.start_point[1])

        self.logger.debug(f"LSP definition result: {definition}")

        if isinstance(definition, list) and len(definition) > 0:
            definition = definition[0]  # 如果是列表，取第一个元素
        else:
            self.logger.debug(f"Definition list is empty or not a list: {definition}")
            return None

        # 基于LSP返回的位置和符号，结合语法树信息和项目结构图，定位目标节点
        callee_fullname = self._find_callee_in_graph_with_context(node, definition, file_path, callee_text)
        return callee_fullname

    def _find_callee_in_graph_with_context(self, node, definition, file_path, callee_text):
        """
        在已有的图结构中，基于LSP和tree-sitter提供的信息搜索目标节点。
        """
        file_path = definition['absolutePath']
        module_name = self._get_module_name(file_path)

        # 从tree-sitter获取函数上下文（包括所属类和方法）
        full_context = self._get_full_context_from_node(node, file_path, callee_text)

        if full_context:
            potential_fullname = f"{module_name}.{full_context}"
            self.logger.debug(f"Trying to find: {potential_fullname} in the graph.")
            if potential_fullname in self.code_graph.graph.nodes:
                self.logger.debug(f"Found callee in graph: {potential_fullname}")
                return potential_fullname

        self.logger.warning(f"Callee {full_context} not found in the existing graph.")
        return None

    def _get_full_context_from_node(self, node, file_path, callee_text):
        """
        使用tree-sitter从AST节点开始向上遍历，逐步构建完整的上下文路径。
        """
        context_parts = [callee_text]
        current_node = node

        self.logger.debug(f"Starting context resolution from node: {callee_text}")

        while current_node:
            if current_node.type == 'function_definition':
                func_name = self._get_node_text(current_node.child_by_field_name('name'), file_path)
                context_parts.insert(0, func_name)  # 从内到外依次插入
                self.logger.debug(f"Found function context: {func_name}")
            elif current_node.type == 'class_definition':
                class_name = self._get_node_text(current_node.child_by_field_name('name'), file_path)
                context_parts.insert(0, class_name)
                self.logger.debug(f"Found class context: {class_name}")
            current_node = current_node.parent

        # 确保类、方法、内嵌函数的上下文都包含在路径中
        full_context = ".".join(context_parts)
        self.logger.debug(f"Full context resolved: {full_context}")
        return full_context

    def _get_node_text(self, node, file_path):
        if node is None:
            return ""
        start_byte = node.start_byte
        end_byte = node.end_byte
        with open(file_path, "r") as file:
            file_content = file.read()
        return file_content[start_byte:end_byte]
