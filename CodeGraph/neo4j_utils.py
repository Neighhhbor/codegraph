import os
import logging
from py2neo import Graph, Node, Relationship
from tqdm import tqdm

class Neo4jHandler:
    def __init__(self, url, user, password):
        self.graph = Graph(url, auth=(user, password))
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Set the desired log level here

    def clean_database(self):
        self.graph.run("MATCH (n) DETACH DELETE n")
        self.logger.debug("数据库已清空")

    def import_graph(self, code_graph):
        nx_graph = code_graph.get_graph()

        # 使用 tqdm 为节点导入添加进度条
        nodes = list(nx_graph.nodes(data=True))
        with tqdm(total=len(nodes), desc="导入节点", unit="节点") as pbar:
            for node, attrs in nodes:
                full_name = node
                node_type = attrs.get('type', 'UNKNOWN').upper()

                if node_type == 'UNKNOWN':
                    tqdm.write(f"发现未知类型的节点: {full_name}")  # 使用 tqdm.write 替代 logger，避免干扰进度条
                    pbar.update(1)
                    continue

                if node_type == 'FILE':
                    short_name = os.path.basename(full_name)
                else:
                    short_name = full_name.split('.')[-1]

                existing_node = self.graph.nodes.match(node_type, full_name=full_name).first()
                if not existing_node:
                    n = Node(node_type, name=short_name, full_name=full_name, code=attrs.get('code', ''), signature=attrs.get('signature', ''), description=attrs.get('description', ''))
                    self.graph.create(n)
                    tqdm.write(f"导入节点: {full_name} (类型: {node_type})")  # 使用 tqdm.write 替代 logger
                pbar.update(1)  # 更新进度条

        # 使用 tqdm 为关系导入添加进度条
        edges = list(nx_graph.edges(data=True))
        with tqdm(total=len(edges), desc="导入关系", unit="关系") as pbar:
            for start, end, edge_attrs in edges:
                start_node = self.graph.nodes.match(full_name=start).first()
                end_node = self.graph.nodes.match(full_name=end).first()
                if start_node and end_node:
                    existing_rel = self.graph.match_one(nodes=(start_node, end_node), r_type=edge_attrs['relationship'])
                    if not existing_rel:
                        rel = Relationship(start_node, edge_attrs['relationship'], end_node)
                        self.graph.create(rel)
                        tqdm.write(f"导入关系: {start} -> {end} (类型: {edge_attrs['relationship']})")  # 使用 tqdm.write 替代 logger
                else:
                    tqdm.write(f"警告: 关系的起始节点或终止节点缺失，跳过创建关系: {start} -> {end}")
                pbar.update(1)  # 更新进度条
