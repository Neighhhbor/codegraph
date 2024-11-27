import os
import sys
import networkx as nx
from tree_sitter import Language, Parser
import tree_sitter_go as tsg
import tree_sitter_java as tsjava
import tree_sitter_python as tspython
import logging
import json
from tqdm import tqdm  # 新增部分，用于进度条
import argparse
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ['go', 'java', 'py']
LANGUAGE_MAP = {
    'go': 'go',
    'java': 'java',
    'py': 'python'
}

EDGE_TYPE_MAP = {
    'dir_to_dir': 1,
    'dir_to_file': 2,
    'file_to_ast': 3,
    'ast_to_ast': 4
}

def export_graph_to_json(graph, file_path):
    with open(file_path, 'w') as f:
        json.dump(nx.node_link_data(graph, edges="links"), f, indent=4)

class RepoParser:
    def __init__(self):
        self.languages = {
            'go': Language(tsg.language()),
            'java': Language(tsjava.language()),
            'python': Language(tspython.language())
        }
        self.parsers = {lang: Parser() for lang in self.languages}
        for lang, parser in self.parsers.items():
            parser.language = self.languages[lang]

        self.node_id_counter = {
            'dir': 0,
            'file': 0,
            'ast': 0
        }
        self.project_graph = nx.MultiDiGraph()
        self.node_index_map = {}

    def generate_node_id(self, node_type):
        # 简洁前缀：d_ 表示目录，f_ 表示文件，a_ 表示AST节点
        prefix = {
            'dir': 'd_',
            'file': 'f_',
            'ast': 'a_'
        }.get(node_type, 'n_')

        # 使用简短的前缀和计数器生成唯一ID
        node_id = f"{prefix}{self.node_id_counter[node_type]}"
        self.node_id_counter[node_type] += 1
        return node_id

    def parse_directory_structure(self, repo_path):
        tree = {"name": os.path.basename(
            repo_path), "type": "directory", "children": []}

        def build_tree(path, node):
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    child = {"name": item, "type": "directory", "children": []}
                    node["children"].append(child)
                    build_tree(item_path, child)
                else:
                    ext = os.path.splitext(item)[1][1:]
                    if ext in SUPPORTED_EXTENSIONS:
                        node["children"].append(
                            {"name": item, "type": "file", "lang": ext, "path": item_path})

        build_tree(repo_path, tree)
        return tree

    def parse_repo(self, repo_path):
        logger.info(f"开始解析仓库: {repo_path}")

        # 统计所有的文件数量，用于进度条显示
        total_files = sum(
            len([item for item in os.listdir(os.path.join(root)) if os.path.isfile(os.path.join(root, item)) and os.path.splitext(item)[1][1:] in SUPPORTED_EXTENSIONS])
            for root, _, _ in os.walk(repo_path)
        )

        # 使用tqdm显示进度条
        with tqdm(total=total_files, desc="Parsing Repository", unit="file") as pbar:
            def process_directory(path, parent_id=None):
                dir_node_id = self.generate_node_id('dir')
                dir_name = os.path.basename(path)
                self.project_graph.add_node(dir_node_id, name=dir_name, type='directory', path=path)
                self.node_index_map[dir_node_id] = len(self.node_index_map)

                if parent_id is not None:
                    self.add_edge(parent_id, dir_node_id, 'CONTAINS', 'dir_to_dir')

                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        process_directory(item_path, dir_node_id)
                    else:
                        ext = os.path.splitext(item)[1][1:]
                        if ext in SUPPORTED_EXTENSIONS:
                            file_node_id = self.generate_node_id('file')
                            self.project_graph.add_node(file_node_id, name=item, type='file', path=item_path, lang=ext)
                            self.node_index_map[file_node_id] = len(self.node_index_map)
                            self.add_edge(dir_node_id, file_node_id, 'CONTAINS', 'dir_to_file')

                            try:
                                self.generate_ast(item_path, file_node_id)
                            except Exception as e:
                                logger.error(f"解析文件 {item_path} 时出错: {e}")
                            finally:
                                # 每处理一个文件，更新进度条
                                pbar.update(1)

            process_directory(repo_path)
        return self.project_graph

    def generate_ast(self, file_path, file_node_id):
        logger.info(f"生成AST: {file_path}")
        ext = os.path.splitext(file_path)[1][1:]
        lang = LANGUAGE_MAP.get(ext)
        if lang is None:
            raise ValueError(f"Unsupported file extension: {ext}")

        with open(file_path, 'rb') as file:
            content = file.read()
        tree = self.parsers[lang].parse(content)
        cursor = tree.walk()

        def traverse(cursor, parent_id=None):
            node = cursor.node
            node_id = self.generate_node_id('ast')
            nodecontent = content[node.start_byte:node.end_byte].decode('utf-8')
            node_data = {
                'id': node_id,
                # 'content': nodecontent,
                'file_id': file_node_id,
                'field_name': cursor.field_name,
                'type': node.type,
                'start_byte': node.start_byte,
                'end_byte': node.end_byte,
                'start_point': node.start_point,
                'end_point': node.end_point,
                'is_named': node.is_named,
                'parent': parent_id,
                'children': []
            }

            if parent_id is None:
                # 文件节点作为AST根节点的父节点
                parent_id = file_node_id

            self.project_graph.add_node(node_id, **node_data)
            self.node_index_map[node_id] = len(self.node_index_map)

            # 添加边到父节点
            if parent_id is not None:
                edge_type = 'file_to_ast' if parent_id == file_node_id else 'ast_to_ast'
                self.add_edge(parent_id, node_id, 'CONTAINS', edge_type)
                self.project_graph.nodes[parent_id].setdefault('children', []).append(node_id)

            if cursor.goto_first_child():
                while True:
                    traverse(cursor, node_id)
                    if not cursor.goto_next_sibling():
                        break
                cursor.goto_parent()

        traverse(cursor)

    def add_edge(self, source, target, relationship, edge_type):
        edge_type_int = EDGE_TYPE_MAP[edge_type]  # 使用EDGE_TYPE_MAP来映射边的类型到整数
        self.project_graph.add_edge(source, target, relationship=relationship, edge_type=edge_type_int)

    def get_edge_type_count(self, edge_type):
        return self.edge_type_counter.get(edge_type, 0)

def save_initial_results(results_dir, project_graph, repo_path):
    with open(os.path.join(results_dir, f'repoparser.json'), 'w') as f:
        json.dump(nx.node_link_data(project_graph, edges="links"), f, indent=4)

def main():
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    
    repo_parser = RepoParser()

    # 解析仓库结构和生成项目图
    project_graph = repo_parser.parse_repo(repo_path)

    # 保存初始解析结果
    save_initial_results(results_dir, project_graph, repo_path)

    print("解析完成。所有结果已导出到output文件夹。")

if __name__ == "__main__":
    main()
