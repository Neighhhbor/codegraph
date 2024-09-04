import networkx as nx
import os
import logging

class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.logger = logging.getLogger(__name__)
        #设置为DEBUG
        self.logger.setLevel(logging.DEBUG)

    def build_graph_from_tree(self, tree_root):
        # 从树的根节点开始构建图
        self._add_node(tree_root)
        self._build_edges(tree_root)

    def _add_node(self, node):
        self.graph.add_node(node.fullname, type=node.node_type, code=node.code, signature=node.signature)
        self.logger.debug(f"添加节点: {node.fullname} (类型: {node.node_type})")

    def _build_edges(self, node):
        for child in node.children:
            self.graph.add_edge(node.fullname, child.fullname, relationship="CONTAINS")
            self._add_node(child)
            self._build_edges(child)

    def add_call(self, caller_fullname, callee_fullname):
        if caller_fullname in self.graph and callee_fullname in self.graph:
            self.graph.add_edge(caller_fullname, callee_fullname, relationship="CALLS")
            self.logger.debug(f"添加调用关系: {caller_fullname} -> {callee_fullname}")
        else:
            self.logger.debug(f"调用关系中的节点不存在: {caller_fullname} -> {callee_fullname}")

    def add_import(self, importer_fullname, imported_fullname):
        if importer_fullname in self.graph and imported_fullname in self.graph:
            self.graph.add_edge(importer_fullname, imported_fullname, relationship="IMPORTS")
            self.logger.debug(f"添加import关系: {importer_fullname} -> {imported_fullname}")
        else:
            self.logger.debug(f"import关系中的节点不存在: {importer_fullname} -> {imported_fullname}")

    def get_graph(self):
        return self.graph
