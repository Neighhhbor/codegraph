from py2neo import Graph, Node, Relationship
import os

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
            full_name = node

            # 根据节点类型选择简化名称的方式
            if attrs['type'].upper() == 'FILE':
                # 文件节点使用文件名作为简化名称
                short_name = os.path.basename(full_name)
            else:
                # 类和函数节点使用最后一个点后的部分作为简化名称
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
