import networkx as nx
import os

class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph_from_tree(self, tree_root):
        # 从树的根节点开始构建图
        self._add_node(tree_root)
        self._build_edges(tree_root)

    def _add_node(self, node):
        self.graph.add_node(node.fullname, type=node.node_type, code=node.code, signature=node.signature)
        print(f"添加节点: {node.fullname} (类型: {node.node_type})")

    def _build_edges(self, node):
        for child in node.children:
            self.graph.add_edge(node.fullname, child.fullname, relationship="CONTAINS")
            self._add_node(child)
            self._build_edges(child)

    def add_call(self, caller_fullname, callee_fullname):
        if caller_fullname in self.graph and callee_fullname in self.graph:
            self.graph.add_edge(caller_fullname, callee_fullname, relationship="CALLS")
            print(f"添加调用关系: {caller_fullname} -> {callee_fullname}")
        else:
            print(f"调用关系中的节点不存在: {caller_fullname} -> {callee_fullname}")

    def get_graph(self):
        return self.graph
