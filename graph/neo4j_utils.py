from py2neo import Graph, Node, Relationship

class Neo4jHandler:
    def __init__(self, url, user, password):
        self.graph = Graph(url, auth=(user, password))

    def clean_database(self):
        """
        清空Neo4j数据库中的所有节点和关系。
        """
        self.graph.run("MATCH (n) DETACH DELETE n")

    def import_graph(self, code_graph):
        nx_graph = code_graph.get_graph()
        for node, attrs in nx_graph.nodes(data=True):
            # 提取最深层的名字（函数名、类名等）
            full_name = node
            if '.' in full_name:
                short_name = full_name.split('.')[-1]
            else:
                short_name = full_name

            # 根据节点类型创建节点
            n = Node(attrs['type'].upper(), name=short_name, full_name=full_name)
            self.graph.merge(n, attrs['type'].upper(), 'full_name')

        for edge in nx_graph.edges(data=True):
            start = self.graph.nodes.match(full_name=edge[0]).first()
            end = self.graph.nodes.match(full_name=edge[1]).first()
            rel = Relationship(start, edge[2]['relationship'], end)
            self.graph.merge(rel)
