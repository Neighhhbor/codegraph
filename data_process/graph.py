import os
import sys
import logging
from tqdm import tqdm  # 导入进度条库
import json
import networkx as nx
from concurrent.futures import ProcessPoolExecutor, as_completed

# 动态添加模块路径
sys.path.append('/home/sxj/Desktop/Workspace/CodeQl/gptgraph/CodeGraph')  # 修改为实际路径

from code_graph import CodeGraph
from parsers.contains_parser import ContainsParser
from parsers.import_parser import ImportParser
from parsers.call_parser import CallParser
from lsp_client import LspClientWrapper

RESULTDIR = "./graphs"
MAX_WORKERS = 8  # 最大并行进程数

# 全局日志配置
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')


# 导出为 JSON 的函数
def export_graph_to_json(graph: nx.DiGraph, output_path: str):
    """
    将 NetworkX 图导出为 JSON 格式并保存到文件。
    :param graph: NetworkX 的 DiGraph 对象
    :param output_path: 要保存的 JSON 文件路径
    """
    graph_data = nx.node_link_data(graph)  # 将图转换为 node-link 格式的字典
    with open(output_path, 'w') as f:
        json.dump(graph_data, f, indent=4)  # 将图数据保存为 JSON 文件
    logging.info(f"Graph saved as JSON to: {output_path}")


def generate_code_graph(repo_path):
    """为给定的代码库生成 JSON 文件。"""
    repo_name = os.path.basename(os.path.normpath(repo_path))
    logging.info(f"Processing repository: {repo_name}")

    # 第一步：解析 CONTAINS 关系
    contains_parser = ContainsParser(repo_path, repo_name)
    contains_parser.parse()

    # 构建代码图
    code_graph = CodeGraph()
    code_graph.build_graph_from_tree(contains_parser.root)

    # 第二步：解析 IMPORT 关系
    import_parser = ImportParser(repo_path, repo_name)
    import_parser.parse()
    for import_data in import_parser.imports:
        importer, imported_module = import_data
        code_graph.add_import(importer, imported_module)

    # 第三步：解析调用关系并启动 LSP 服务器
    lsp_client = LspClientWrapper(repo_path)
    lsp_client.start_server()

    try:
        call_parser = CallParser(repo_path, repo_name, code_graph, contains_parser.defined_symbols, lsp_client)
        call_parser.parse()

        for caller, callee in call_parser.calls:
            code_graph.add_call(caller, callee)
    finally:
        lsp_client.stop_server()

    # 保存代码图为 JSON 文件
    os.makedirs(RESULTDIR, exist_ok=True)
    json_path = os.path.join(RESULTDIR, f"{repo_name}.json")

    # NetworkX graph is stored in the code_graph object; let's assume it has an attribute that holds the DiGraph
    nx_graph = code_graph.graph  # 假设 code_graph.graph 是 NetworkX 的 DiGraph 对象
    export_graph_to_json(nx_graph, json_path)


def process_repositories(base_dir):
    """遍历目录并为每个代码库生成 JSON 文件，使用并发处理。"""
    repos = []
    for category in os.listdir(base_dir):
        category_path = os.path.join(base_dir, category)
        if os.path.isdir(category_path):
            for repo in os.listdir(category_path):
                repo_path = os.path.join(category_path, repo)
                if os.path.isdir(repo_path):
                    repos.append(repo_path)

    # 使用进程池并发处理每个代码库，限制最大并发数为 MAX_WORKERS
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务并返回未来对象
        future_to_repo = {executor.submit(generate_code_graph, repo_path): repo_path for repo_path in repos}

        # 使用 tqdm 显示进度条并处理完成的任务
        for future in tqdm(as_completed(future_to_repo), total=len(repos), desc="Processing repositories"):
            repo_path = future_to_repo[future]
            try:
                future.result()  # 获取任务的结果，如果有异常则抛出
            except Exception as exc:
                logging.error(f"Repo {repo_path} generated an exception: {exc}")


if __name__ == "__main__":
    base_dir = '/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Repos'  # 根据你的实际路径设置
    process_repositories(base_dir)
