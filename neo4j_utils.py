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
                short_name = full_name.split('.')[-1]

            existing_node = self.graph.nodes.match(node_type, full_name=full_name).first()
            if not existing_node:
                n = Node(node_type, name=short_name, full_name=full_name, code=attrs.get('code', ''), signature=attrs.get('signature', ''), description=attrs.get('description', ''))
                self.graph.create(n)
                print(f"导入节点: {full_name} (类型: {node_type})")

        for start, end, edge_attrs in nx_graph.edges(data=True):
            start_node = self.graph.nodes.match(full_name=start).first()
            end_node = self.graph.nodes.match(full_name=end).first()
            if start_node and end_node:
                existing_rel = self.graph.match_one(nodes=(start_node, end_node), r_type=edge_attrs['relationship'])
                if not existing_rel:
                    rel = Relationship(start_node, edge_attrs['relationship'], end_node)
                    self.graph.create(rel)
                    print(f"导入关系: {start} -> {end} (类型: {edge_attrs['relationship']})")
            else:
                print(f"警告: 关系的起始节点或终止节点缺失，跳过创建关系: {start} -> {end}")
