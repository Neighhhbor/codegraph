import os
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
import logging

class ImportParser:
    def __init__(self, project_path, repo_name):
        self.project_path = project_path
        self.repo_name = repo_name
        self.parser = self._init_parser()
        self.imports = []  # 存储import关系 (importer, imported_module)

        # 配置日志记录
        self.logger = logging.getLogger('import_parser')
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _init_parser(self):
        PY_LANGUAGE = Language(tspython.language())
        parser = Parser(PY_LANGUAGE)
        return parser

    def parse(self):
        """
        解析项目中的所有 Python 文件并提取导入关系
        """
        py_files = self._get_py_files()
        self.logger.debug(f"Found {len(py_files)} Python files to parse.")
        for file in py_files:
            self.logger.debug(f"Parsing file: {file}")
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

        tree = self.parser.parse(bytes(file_content, "utf8"))

        # 构建模块名称
        module_name = self._get_module_name(file_path)
        self.logger.debug(f"Module name for file {file_path}: {module_name}")

        # 递归分析import关系
        self._extract_imports(tree.root_node, file_path, module_name)

    def _get_module_name(self, file_path):
        """
        生成基于文件路径的模块名称
        """
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _extract_imports(self, node, file_path, current_fullname):
        """
        递归解析文件中的 import 语句
        """
        for child in node.children:
            if child.type == 'import_statement':
                self.logger.debug(f"Found import statement in {current_fullname}")
                # 处理import语句
                self._handle_import_statement(child, current_fullname, file_path)

            elif child.type == 'import_from_statement':
                self.logger.debug(f"Found from-import statement in {current_fullname}")
                # 处理 from ... import ... 语句
                self._handle_from_import_statement(child, current_fullname, file_path)

            else:
                # 递归处理其他子节点
                self._extract_imports(child, file_path, current_fullname)

    def _handle_import_statement(self, node, current_fullname, file_path):
        """
        处理普通的 import 语句
        """
        for name_node in node.named_children:
            if name_node.type == 'dotted_name' or name_node.type == 'identifier':
                import_name = self._get_node_text(name_node, file_path)
                self.imports.append((current_fullname, import_name))
                self.logger.debug(f"Recorded import: {current_fullname} imports {import_name}")
            # 处理别名（as导入）
            alias_node = node.child_by_field_name('alias')
            if alias_node:
                alias_name = self._get_node_text(alias_node, file_path)
                self.imports.append((current_fullname, alias_name))
                self.logger.debug(f"Recorded alias import: {current_fullname} imports {alias_name}")

    def _handle_from_import_statement(self, node, current_fullname, file_path):
        """
        处理 from ... import ... 语句
        """
        module_name_node = node.child_by_field_name('module')
        module_name = self._get_node_text(module_name_node, file_path) if module_name_node else None

        if module_name:
            # 记录从模块导入的关系
            self.imports.append((current_fullname, module_name))
            self.logger.debug(f"Recorded from-import: {current_fullname} imports from {module_name}")
            
            # 处理具体导入的元素
            for import_child in node.named_children:
                if import_child.type == 'dotted_name' or import_child.type == 'identifier':
                    import_element = self._get_node_text(import_child, file_path)
                    full_import_path = f"{module_name}.{import_element}"
                    self.imports.append((current_fullname, full_import_path))
                    self.logger.debug(f"Recorded from-import element: {current_fullname} imports {full_import_path}")
                # 处理别名导入
                alias_node = node.child_by_field_name('alias')
                if alias_node:
                    alias_name = self._get_node_text(alias_node, file_path)
                    full_alias_path = f"{module_name}.{alias_name}"
                    self.imports.append((current_fullname, full_alias_path))
                    self.logger.debug(f"Recorded alias from-import: {current_fullname} imports {full_alias_path}")

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
