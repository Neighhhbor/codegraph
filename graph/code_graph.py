import networkx as nx
import os

class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_file(self, file_name):
        short_name = os.path.basename(file_name)
        self.graph.add_node(file_name, type="file", display_name=short_name)
        print(f"添加文件节点: {file_name}")

    def add_class(self, class_name, file_name):
        class_full_name = class_name
        short_name = class_name.split('.')[-1]
        if not self.graph.has_node(class_full_name):
            self.graph.add_node(class_full_name, type="class", display_name=short_name)
            self.graph.add_edge(file_name, class_full_name, relationship="CONTAINS")
            print(f"添加类节点: {class_full_name}，属于文件: {file_name}")
        else:
            print(f"类节点已存在: {class_full_name}")

    def add_function(self, func_name, container_name):
        func_full_name = func_name
        short_name = func_name.split('.')[-1]

        if not self.graph.has_node(func_full_name):
            print(f"添加函数节点: {func_full_name}，属于容器: {container_name}")
            self.graph.add_node(func_full_name, type="function", display_name=short_name)
            self.graph.add_edge(container_name, func_full_name, relationship="CONTAINS")
        else:
            print(f"函数节点已存在: {func_full_name}")


    def add_call(self, caller, callee):
        caller_full_name = self._resolve_function_name(caller)
        callee_full_name = self._resolve_function_name(callee)

        if caller_full_name and callee_full_name:
            self.graph.add_edge(caller_full_name, callee_full_name, relationship="CALLS")
            print(f"添加调用关系: {caller_full_name} -> {callee_full_name}")
        else:
            if not caller_full_name:
                print(f"警告: 找不到调用者节点: {caller}")
            if not callee_full_name:
                print(f"警告: 找不到被调用者节点: {callee}")

    def _resolve_function_name(self, func_name):
        # 优先匹配完整的类成员函数名称
        for full_name in self.graph.nodes:
            if full_name.endswith(func_name) and self.graph.nodes[full_name]['type'] == 'function':
                return full_name
        # 如果找不到类成员函数，再考虑文件级别的函数
        for full_name in self.graph.nodes:
            if full_name.endswith(func_name.split('.')[-1]) and self.graph.nodes[full_name]['type'] == 'function':
                return full_name
        print(f"警告: 未能解析函数名: {func_name}")
        return None



    def get_graph(self):
        return self.graph
