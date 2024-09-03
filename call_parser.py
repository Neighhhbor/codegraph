import os
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
from lsp_client import LspClientWrapper
import logging

class CallParser:
    def __init__(self, project_path, repo_name, code_graph):
        self.project_path = project_path
        self.repo_name = repo_name
        self.code_graph = code_graph
        self.calls = []

        self.defined_identifiers = set()  # 用于存储项目内定义的标识符

        self.parser = self._init_parser()
        self.lsp_client = LspClientWrapper(project_root=project_path)

        self.logger = logging.getLogger('call_parser')
        self.logger.setLevel(logging.DEBUG)

    def _init_parser(self):
        PY_LANGUAGE = Language(tspython.language())
        parser = Parser(PY_LANGUAGE)
        return parser

    def parse(self):
        for file in self._get_py_files():
            self.logger.debug(f"Parsing file: {file}")
            self._register_identifiers(file)
            self._parse_file(file)

    def _get_py_files(self):
        return [os.path.join(root, file)
                for root, _, files in os.walk(self.project_path)
                for file in files if file.endswith(".py")]

    def _register_identifiers(self, file_path):
        """第一遍扫描，注册项目内定义的标识符"""
        with open(file_path, "r") as file:
            tree = self.parser.parse(bytes(file.read(), "utf8"))

        self._collect_identifiers(tree.root_node, file_path)

    def _collect_identifiers(self, node, file_path):
        """递归收集所有定义的标识符（函数、类）"""
        for child in node.children:
            if child.type in ['class_definition', 'function_definition']:
                name_node = child.child_by_field_name('name')
                if name_node:
                    identifier_name = self._get_node_text(name_node, file_path)
                    self.defined_identifiers.add(identifier_name)
                    self.logger.debug(f"Registered identifier: {identifier_name}")
            self._collect_identifiers(child, file_path)

    def _parse_file(self, file_path):
        with open(file_path, "r") as file:
            tree = self.parser.parse(bytes(file.read(), "utf8"))

        module_name = self._get_module_name(file_path)
        self.logger.debug(f"Module name: {module_name}")

        self._extract_calls(tree.root_node, file_path, module_name)

    def _get_module_name(self, file_path):
        relative_path = os.path.relpath(file_path, self.project_path)
        return f"{self.repo_name}.{os.path.splitext(relative_path)[0].replace(os.path.sep, '.')}"

    def _extract_calls(self, node, file_path, current_fullname):
        for child in node.children:
            if child.type == 'class_definition':
                class_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                self._extract_calls(child, file_path, f"{current_fullname}.{class_name}")
            elif child.type == 'function_definition':
                func_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                self._extract_calls(child, file_path, f"{current_fullname}.{func_name}")
            elif child.type == 'call':
                callee_name = self._resolve_callee_name(child, file_path)
                if callee_name:
                    self.calls.append((current_fullname, callee_name))
                    self.logger.debug(f"Added call: {current_fullname} -> {callee_name}")
            else:
                self._extract_calls(child, file_path, current_fullname)

    def _resolve_callee_name(self, node, file_path):
        func_node = node.child_by_field_name('function')
        if not func_node:
            return None

        callee_text = self._get_node_text(func_node, file_path)
        self.logger.debug(f"Resolved callee name from tree-sitter: {callee_text}")

        # 如果被调用的标识符在定义的集合中，使用 LSP 进行解析
        if callee_text in self.defined_identifiers:
            self.logger.debug(f"Callee '{callee_text}' found in defined identifiers, using LSP to resolve.")
            definition = self.lsp_client.find_definition(file_path, func_node.start_point[0], func_node.start_point[1])
            self.logger.debug(f"LSP definition result: {definition}")

            if not definition:
                return None

            definition = definition[0] if isinstance(definition, list) else definition
            return self._find_callee_in_graph(node, definition, callee_text, file_path)
        else:
            # 如果标识符不在项目定义中，跳过进一步解析
            self.logger.debug(f"Callee '{callee_text}' not found in defined identifiers, skipping LSP.")
            return None

    def _find_callee_in_graph(self, node, definition, callee_text, file_path):
        if definition['uri'] != f"file://{file_path}":
            file_path = definition['absolutePath']

        module_name = self._get_module_name(file_path)
        full_context = self._get_full_context(node, file_path, callee_text)

        potential_fullname = f"{module_name}.{full_context}"
        if potential_fullname in self.code_graph.graph.nodes:
            self.logger.debug(f"Found callee in graph: {potential_fullname}")
            return potential_fullname

        self.logger.warning(f"Callee {potential_fullname} not found in the existing graph.")
        return None

    def _get_full_context(self, node, file_path, callee_text):
        context_parts = [callee_text]
        current_node = node

        self.logger.debug(f"Starting context resolution from node: {callee_text}")

        while current_node:
            if current_node.type in ['function_definition', 'class_definition']:
                name_node = current_node.child_by_field_name('name')
                if name_node:
                    context_parts.insert(0, self._get_node_text(name_node, file_path))
            elif current_node.type == 'module':
                self.logger.debug("Reached module level, stopping context resolution.")
                break

            current_node = current_node.parent

        if len(context_parts) == 1:
            module_name = self._get_module_name(file_path)
            full_context = f"{module_name}.{callee_text}"
            self.logger.debug(f"Top-level function detected, using full context: {full_context}")
            return full_context

        full_context = ".".join(context_parts).strip()
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
