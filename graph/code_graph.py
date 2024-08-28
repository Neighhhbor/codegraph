import networkx as nx

class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_file(self, file_name):
        self.graph.add_node(file_name, type="file")

    def add_class(self, class_name, file_name):
        class_full_name = f"{file_name}.{class_name}"
        if not self.graph.has_node(class_full_name):
            self.graph.add_node(class_full_name, type="class")
            self.graph.add_edge(file_name, class_full_name, relationship="CONTAINS")

    def add_function(self, func_name, container_name):
        func_full_name = func_name
        if not self.graph.has_node(func_full_name):
            self.graph.add_node(func_full_name, type="function")
            self.graph.add_edge(container_name, func_full_name, relationship="CONTAINS")

    def add_call(self, caller, callee):
        # 确保调用的节点已经存在图中，避免重复创建
        if not self.graph.has_node(caller):
            self.graph.add_node(caller, type="function")
        if not self.graph.has_node(callee):
            self.graph.add_node(callee, type="function")
        self.graph.add_edge(caller, callee, relationship="CALLS")

    def get_graph(self):
        return self.graph
