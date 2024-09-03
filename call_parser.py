import os
import re
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
import logging
from lsp_client import LspClientWrapper

class CallParser:
    def __init__(self, project_path, repo_name, code_graph):
        self.project_path = project_path
        self.repo_name = repo_name
        self.code_graph = code_graph
        self.parser = self._init_parser()
        self.calls = []  # 存储调用关系 (caller, callee)
        self.defined_symbols = {}  # 存储所有定义的标识符，格式为 {name: [module_name1, module_name2,...]}

        # 配置日志记录
        self.logger = logging.getLogger('call_parser')
        self.logger.setLevel(logging.INFO)  # 设置为INFO模式以输出详细信息
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # 初始化LSP客户端
        self.lsp_client = LspClientWrapper(self.project_path)

    def _init_parser(self):
        PY_LANGUAGE = Language(tspython.language())
        parser = Parser(PY_LANGUAGE)
        return parser

    def parse(self):
        py_files = self._get_py_files()
        self.logger.debug(f"Found {len(py_files)} Python files to parse.")
        
        # 第一遍扫描：注册所有标识符
        for file in py_files:
            self.logger.debug(f"Scanning definitions in file: {file}")
            self._scan_definitions(file)
        
        # 第二遍解析：处理调用关系
        for file in py_files:
            self.logger.debug(f"Parsing calls in file: {file}")
            self._parse_file(file)

    def _get_py_files(self):
        py_files = []
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
        return py_files

    def _get_module_name(self, file_path):
        """根据文件路径生成模块全名"""
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _remove_comments(self, code):
        """移除Python代码中的注释"""
        # 移除单行注释
        code = re.sub(r'#.*', '', code)
        # 移除多行字符串（包括注释）
        code = re.sub(r'\'\'\'(.*?)\'\'\'', '', code, flags=re.DOTALL)
        code = re.sub(r'\"\"\"(.*?)\"\"\"', '', code, flags=re.DOTALL)
        return code

    def _scan_definitions(self, file_path):
        with open(file_path, "r") as file:
            file_content = file.read()

        # 去掉注释
        file_content = self._remove_comments(file_content)

        tree = self.parser.parse(bytes(file_content, "utf8"))

        # 构建模块名称
        module_name = self._get_module_name(file_path)
        self._register_definitions(tree.root_node, file_path, module_name)

    def _register_definitions(self, node, file_path, current_fullname):
        for child in node.children:
            if child.type == 'class_definition' or child.type == 'function_definition':
                # 只注册函数名或类名，不包含路径
                name = self._get_node_text(child.child_by_field_name('name'), file_path)
                if name in self.defined_symbols:
                    self.defined_symbols[name].append(current_fullname)
                else:
                    self.defined_symbols[name] = [current_fullname]
                # 递归处理子节点
                self._register_definitions(child, file_path, current_fullname)
            else:
                # 继续递归处理其他子节点
                self._register_definitions(child, file_path, current_fullname)

    def _parse_file(self, file_path):
        with open(file_path, "r") as file:
            file_content = file.read()

        # 去掉注释
        file_content = self._remove_comments(file_content)

        tree = self.parser.parse(bytes(file_content, "utf8"))

        # 构建模块名称
        module_name = self._get_module_name(file_path)

        # 递归分析调用关系
        self._extract_calls(tree.root_node, file_path, module_name)

    def _extract_calls(self, node, file_path, current_fullname):
        for child in node.children:
            if child.type == 'function_definition':
                func_name = self._get_node_text(child.child_by_field_name('name'), file_path)
                func_fullname = f"{current_fullname}.{func_name}"

                # 递归分析函数体内的调用
                self._extract_calls(child, file_path, func_fullname)

            elif child.type == 'call':
                func_name_node = child.child_by_field_name('function')
                if func_name_node:
                    callee_name = self._get_node_text(func_name_node, file_path)

                    if callee_name in self.defined_symbols:
                        # 获取定义路径列表
                        definition_paths = self.defined_symbols[callee_name]

                        if len(definition_paths) == 1:
                            # 唯一定义，直接使用
                            callee_fullname = definition_paths[0] + '.' + callee_name
                            self.calls.append((current_fullname, callee_fullname))
                            self.logger.info(f"Recorded call: {current_fullname} -> {callee_fullname}")

                        else:
                            # 多个定义，使用 LSP 确定具体定义
                            definition = self.lsp_client.find_definition(file_path, func_name_node.start_point[0], func_name_node.start_point[1])
                            if definition:
                                callee_fullname = self._get_fullname_from_definition(definition)
                                if callee_fullname and any(callee_fullname.startswith(path) for path in definition_paths):
                                    self.calls.append((current_fullname, callee_fullname))
                                    self.logger.info(f"Recorded call: {current_fullname} -> {callee_fullname}")
                                else:
                                    self.logger.warning(f"Could not determine the correct definition for {callee_name} called in {current_fullname}")

                    else:
                        self.logger.info(f"Call to external function {callee_name} in {current_fullname}, skipping.")

            elif child.type == 'attribute':
                # 处理成员函数或静态方法调用
                object_name_node = child.child_by_field_name('object')
                method_name_node = child.child_by_field_name('attribute')

                object_name = self._get_node_text(object_name_node, file_path) if object_name_node else None
                method_name = self._get_node_text(method_name_node, file_path) if method_name_node else None

                if object_name and method_name:
                    if method_name in self.defined_symbols:
                        definition_paths = self.defined_symbols[method_name]

                        if len(definition_paths) == 1:
                            # 唯一定义，直接使用
                            callee_fullname = definition_paths[0] + '.' + method_name
                            self.calls.append((current_fullname, callee_fullname))
                            self.logger.info(f"Recorded method call: {current_fullname} -> {callee_fullname}")

                        else:
                            # 多个定义，使用 LSP 确定具体定义
                            definition = self.lsp_client.find_definition(file_path, method_name_node.start_point[0], method_name_node.start_point[1])
                            if definition:
                                callee_fullname = self._get_fullname_from_definition(definition)
                                if callee_fullname and any(callee_fullname.startswith(path) for path in definition_paths):
                                    self.calls.append((current_fullname, callee_fullname))
                                    self.logger.info(f"Recorded method call: {current_fullname} -> {callee_fullname}")
                                else:
                                    self.logger.warning(f"Could not determine the correct definition for {method_name} called in {current_fullname}")

                else:
                    self.logger.error(f"Failed to extract method call details in {current_fullname}: object_name={object_name}, method_name={method_name}")

            else:
                # 递归处理其他子节点
                self._extract_calls(child, file_path, current_fullname)


    def _get_node_text(self, node, file_path):
        if node is None:
            return ""
        start_byte = node.start_byte
        end_byte = node.end_byte
        with open(file_path, "r") as file:
            file_content = file.read()
        return file_content[start_byte:end_byte]

    def _get_fullname_from_definition(self, definition):
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
