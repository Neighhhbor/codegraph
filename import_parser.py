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
        self.logger.setLevel(logging.DEBUG)  # 设置为DEBUG模式以输出详细信息
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _init_parser(self):
        language = Language(tspython.language(), 'python')
        parser = Parser()
        parser.set_language(language)
        return parser

    def parse(self):
        py_files = self._get_py_files()
        self.logger.debug(f"Found {len(py_files)} Python files to parse.")
        for file in py_files:
            self.logger.info(f"Parsing file: {file}")
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
        self.logger.debug(f"Module name for file {file_path}: {module_name}")

        # 递归分析import关系
        self._extract_imports(tree.root_node, file_path, module_name)

    def _get_module_name(self, file_path):
        relative_path = os.path.relpath(file_path, self.project_path)
        module_name = os.path.splitext(relative_path)[0].replace(os.path.sep, '.')
        return f"{self.repo_name}.{module_name}"

    def _extract_imports(self, node, file_path, current_fullname):
        for child in node.children:
            if child.type == 'import_statement':
                self.logger.debug(f"Found import statement in {current_fullname}")
                # 处理import关系，记录import的模块
                for name_node in child.named_children:
                    if name_node.type == 'dotted_name' or name_node.type == 'identifier':
                        import_name = self._get_node_text(name_node, file_path)
                        self.imports.append((current_fullname, import_name))
                        self.logger.info(f"Recorded import: {current_fullname} imports {import_name}")

            elif child.type == 'import_from_statement':
                self.logger.debug(f"Found from-import statement in {current_fullname}")
                # 处理from ... import ...形式的导入
                module_name_node = child.child_by_field_name('module')
                module_name = self._get_node_text(module_name_node, file_path) if module_name_node else None

                if module_name:
                    self.imports.append((current_fullname, module_name))
                    self.logger.info(f"Recorded import: {current_fullname} imports from {module_name}")

            else:
                # 递归处理其他子节点
                self._extract_imports(child, file_path, current_fullname)

    def _get_node_text(self, node, file_path):
        if node is None:
            return ""
        start_byte = node.start_byte
        end_byte = node.end_byte
        with open(file_path, "r") as file:
            file_content = file.read()
        return file_content[start_byte:end_byte]
