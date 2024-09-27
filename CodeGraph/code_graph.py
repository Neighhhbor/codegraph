import networkx as nx
import sys
import importlib.util
import logging


class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def build_graph_from_tree(self, tree_root):
        # 从树的根节点开始构建图
        self._add_node(tree_root)
        self._build_edges(tree_root)

    def _add_node(self, node):
        self.graph.add_node(node.fullname, type=node.node_type,
                            code=node.code, signature=node.signature)
        self.logger.debug(f"添加节点: {node.fullname} (类型: {node.node_type})")

    def _build_edges(self, node):
        for child in node.children:
            self.graph.add_edge(node.fullname, child.fullname,
                                relationship="CONTAINS")
            self._add_node(child)
            self._build_edges(child)

    def add_call(self, caller_fullname, callee_fullname):
        if caller_fullname in self.graph and callee_fullname in self.graph:
            self.graph.add_edge(
                caller_fullname, callee_fullname, relationship="CALLS")
            self.logger.debug(
                f"添加调用关系: {caller_fullname} -> {callee_fullname}")
        else:
            self.logger.debug(
                f"调用关系中的节点不存在: {caller_fullname} -> {callee_fullname}")

    def add_import(self, importer_fullname, imported_fullname):
        # 检测模块类型
        module_type, module_path = self._detect_module_type(imported_fullname)

        # 如果模块不存在图中，为第三方库、标准库或本地库创建虚拟节点
        if imported_fullname not in self.graph:
            self.logger.debug(f"创建节点: {imported_fullname} (类型: {
                              module_type}) 路径: {module_path}")
            self.graph.add_node(imported_fullname,
                                type=module_type, code=None, signature=None)

        if importer_fullname in self.graph:
            self.graph.add_edge(importer_fullname,
                                imported_fullname, relationship="IMPORTS")
            self.logger.debug(
                f"添加import关系: {importer_fullname} -> {imported_fullname}")
        else:
            self.logger.debug(f"import关系中的节点不存在: {
                              importer_fullname} -> {imported_fullname}")

    def _detect_module_type(self, module_name):
        """
        检测模块类型：标准库、第三方库或本地库
        """
        try:
            # 检测标准库模块
            if module_name in sys.builtin_module_names:
                return "standard_library", None

            # 使用 importlib.util.find_spec 查找模块的元信息
            module_spec = importlib.util.find_spec(module_name)
            if module_spec is None:
                self.logger.debug(f"无法找到模块 {module_name}")
                return "unknown", None

            # 判断模块类型：第三方库或标准库
            module_path = module_spec.origin
            if not module_path:
                return "unknown", None

            if "site-packages" in module_path or "dist-packages" in module_path:
                return "third_party_library", module_path
            else:
                return "local_module", module_path

        except ModuleNotFoundError:
            self.logger.debug(f"模块 {module_name} 未安装")
            return "unknown", None

        except ValueError as e:
            # 捕获 ValueError 并记录日志
            self.logger.error(f"检测模块 {module_name} 时出现 ValueError: {e}")
            return "unknown", None

    def get_graph(self):
        return self.graph