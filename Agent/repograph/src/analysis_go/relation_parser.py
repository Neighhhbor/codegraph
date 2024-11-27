import networkx as nx
import json
import os
import sys
from tqdm import tqdm  # Import tqdm for progress bar
import logging  # 使用 logging 代替 print
from repo_parser import EDGE_TYPE_MAP  # Assuming this module provides EDGE_TYPE_MAP
import argparse
# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别
    format='%(asctime)s - %(levelname)s - %(message)s',
)

DEFINITION_TYPE = ["function_declaration", "method_declaration", "var_declaration"]


class GraphBuilder:
    def __init__(self, graph):
        self.graph = graph
        self.file_cache = {}  # Cache for file contents to avoid repeated reads
        self.counter0 = 0
        self.counter1 = 0
        self.counter2 = 0
        self.counter3 = 0

    def build_contains_relationship(self):
        """Build CONTAINS relationships with progress tracking."""
        total_nodes = len(self.graph.nodes)
        with tqdm(total=total_nodes, desc="构建 CONTAINS 关系", unit="node") as pbar:
            for node_id, node_data in self.graph.nodes(data=True):
                if node_id.startswith("a_"):
                    parent_id = node_data.get("parent")
                    if parent_id is None:
                        pbar.update(1)
                        continue

                    nodetype = {"a": "ast", "f": "file", "d": "dir"}
                    sourcetype = nodetype[parent_id.split("_")[0]]
                    targettype = nodetype[node_id.split("_")[0]]
                    edgetype = f"{sourcetype}_to_{targettype}"

                    if not self.edge_exists(parent_id, node_id, "CONTAINS", edgetype):
                        self.add_edge(parent_id, node_id, "CONTAINS", edgetype)

                pbar.update(1)

    def build_calls_relationship(self):
        """Build CALLS relationships with progress tracking."""
        total_nodes = len(self.graph.nodes)
        with tqdm(total=total_nodes, desc="构建 CALLS 关系", unit="node") as pbar:
            for node_id, node_data in self.graph.nodes(data=True):
                if node_id.startswith("a_"):
                    if node_data["type"] == "call_expression":
                        self.counter0 += 1
                        caller_id = self.find_parent_method(node_id)
                        callee_id = self.find_identifier(node_id)
                        logging.info(f"caller_id: {caller_id}, callee_id: {callee_id}")
                        if caller_id and callee_id:
                            self.counter1 += 1
                            logging.info(f"caller_id: {caller_id}, callee_id: {callee_id}")
                            if "defid" in self.graph.nodes[callee_id]:
                                self.counter2 += 1
                                callee_id = self.graph.nodes[callee_id]["defid"]
                                logging.debug(f"callee_id: {callee_id}")
                                if "function_id" in self.graph.nodes[callee_id]:
                                    func_id = self.graph.nodes[callee_id]["function_id"]
                                    logging.debug(f"func_id: {func_id}")
                                    self.counter3 += 1
                                    if caller_id != func_id:
                                        self.add_edge(caller_id, func_id, "CALLS", "ast_to_ast")
                                        logging.info(f"添加 CALLS 关系: {caller_id} -> {func_id}")
                                else:
                                    logging.debug(f"def_id: {callee_id} 不是repo内定义的函数")
                            else:
                                logging.debug(f"callee_id: {callee_id} 没有 defid")
                            # logging.info(f"内容: {self.graph.nodes[callee_id]['content']}")
                            logging.info("*" * 100)

                pbar.update(1)

    def find_parent_method(self, node_id):
        """Find the parent method declaration of a node."""
        father_id = None
        while node_id:
            node_data = self.graph.nodes.get(node_id)
            logging.debug(f"node_id: {node_id}, node_type: {node_data['type']}")
            if node_data and node_data["type"] in DEFINITION_TYPE:
                father_id = node_id
                return father_id
            node_id = node_data.get("parent")
        if father_id is None:
            return None

    def find_identifier(self, node_id):
        """Find the identifier child node for a call expression."""
        children = self.graph.nodes[node_id].get("children", [])
        for child_id in children:
            child_node = self.graph.nodes.get(child_id)
            logging.debug(f"child_id: {child_id}, child_node_type: {child_node['type']}")
            if child_node and child_node["field_name"] == "function" and child_node["type"] == "selector_expression":
                for grandchild_id in child_node.get("children", []):
                    grandchild_node = self.graph.nodes.get(grandchild_id)
                    if grandchild_node and grandchild_node["field_name"] == "field" and grandchild_node["type"] == "field_identifier":
                        return grandchild_id
            elif child_node and child_node["field_name"] == "function" and child_node["type"] == "identifier":
                return child_id
        return None

    def load_file_content(self, file_path):
        """Load and cache file content to avoid repeated reads."""
        if file_path not in self.file_cache:
            with open(file_path, 'r') as f:
                self.file_cache[file_path] = f.read()
        return self.file_cache[file_path]

    def add_edge(self, source, target, relationship, edge_type):
        """Add an edge to the graph, avoiding duplicates."""
        edge_type_int = EDGE_TYPE_MAP[edge_type]

        if not self.edge_exists(source, target, relationship, edge_type_int):
            self.graph.add_edge(source, target, relationship=relationship, edge_type=edge_type_int)

    def edge_exists(self, source, target, relationship, edge_type):
        """Check if an edge with the same relationship and type already exists."""
        edge_data = self.graph.get_edge_data(source, target, default={})
        for data in edge_data.values():
            if data.get("relationship") == relationship and data.get("edge_type") == edge_type:
                return True
        return False


def main():
    """主程序入口，加载现有图并构建关系。"""
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    graph_path = os.path.join(results_dir, 'funcid_graph.json')
    output_path = os.path.join(results_dir, 'relation_graph.json')
    try:
        with open(graph_path, 'r') as f:
            graph = nx.node_link_graph(json.load(f), edges="links")
            logging.info(f"成功加载图: {graph_path}")
    except FileNotFoundError:
        logging.error(f"未找到图文件: {graph_path}")
        return

    builder = GraphBuilder(graph)

    # 构建 CONTAINS 和 CALLS 关系
    builder.build_contains_relationship()
    builder.build_calls_relationship()
    print(f"counter0: {builder.counter0}, counter1: {builder.counter1}, counter2: {builder.counter2}, counter3: {builder.counter3}")
    try:
        with open(output_path, 'w') as f:
            json.dump(nx.node_link_data(graph, edges="links"), f, indent=4)
            logging.info(f"图已成功保存到: {output_path}")
    except Exception as e:
        logging.error(f"保存图时出错: {e}")


if __name__ == "__main__":
    main()
