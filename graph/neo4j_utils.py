from py2neo import Graph, Node, Relationship
import os

class Neo4jHandler:
    def __init__(self, url, user, password):
        self.graph = Graph(url, auth=(user, password))

    def clean_database(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        print("数据库已清空")

    def import_graph(self, code_graph):
        nx_graph = code_graph.get_graph()
        for node, attrs in nx_graph.nodes(data=True):
            full_name = node
            node_type = attrs.get('type', 'UNKNOWN').upper()

            if node_type == 'UNKNOWN':
                print(f"发现未知类型的节点: {full_name}")
                continue

            if node_type == 'FILE':
                short_name = os.path.basename(full_name)
            else:
                if '.' in full_name:
                    short_name = full_name.split('.')[-1]
                else:
                    short_name = full_name

            n = Node(node_type, name=short_name, full_name=full_name)
            self.graph.merge(n, node_type, 'full_name')
            print(f"导入节点: {full_name} (类型: {node_type})")

        for edge in nx_graph.edges(data=True):
            start = self.graph.nodes.match(full_name=edge[0]).first()
            end = self.graph.nodes.match(full_name=edge[1]).first()
            if start is None or end is None:
                print(f"警告: 关系的起始节点或终止节点缺失，跳过创建关系: {edge}")
                continue
            rel = Relationship(start, edge[2]['relationship'], end)
            self.graph.merge(rel)
            print(f"导入关系: {edge[0]} -> {edge[1]} (类型: {edge[2]['relationship']})")
