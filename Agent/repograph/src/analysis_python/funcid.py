import networkx as nx
import json
import logging
from tqdm import tqdm  # 引入 tqdm 进度条库
import argparse
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为 INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)  # 创建日志记录器

def find_function_declaration_ancestor(graph, node_id):
    """
    从 identifier 节点向上查找其最近的 function_definition 祖先节点。
    """
    while node_id:
        node_data = graph.nodes.get(node_id)
        if node_data and node_data.get("type") == "function_definition":
            return node_id  # 找到最近的 function_definition 祖先节点
        if node_data and node_data.get("type") == "module":
            break  # 遇到根节点则停止
        node_id = node_data.get("parent")
    return None

def add_function_id_to_nodes(graph):
    """
    在每个 identifier 节点上添加 function_id 字段，用于指向其所属的 function_definition 节点。
    """
    nodes = list(graph.nodes(data=True))
    for node_id, node_data in tqdm(nodes, desc="Adding function_id to Nodes"):
        if node_data.get("type") == "identifier":
            function_id = find_function_declaration_ancestor(graph, node_id)
            if function_id:
                node_data["function_id"] = function_id
                logger.debug(f"节点 {node_id} 的 function_id 为 {function_id}")

def load_graph(input_path):
    """
    从 JSON 文件加载图数据。
    """
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
        graph = nx.node_link_graph(data)
        logger.info(f"成功加载图: {input_path}")
        return graph
    except FileNotFoundError:
        logger.error(f"未找到图文件: {input_path}")
        return None
    except Exception as e:
        logger.error(f"加载图时出错: {e}")
        return None

def save_graph(graph, output_path):
    """
    将处理后的图保存为 JSON 文件。
    """
    try:
        data = nx.node_link_data(graph)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"图已成功保存到: {output_path}")
    except Exception as e:
        logger.error(f"保存图时出错: {e}")

def main():
    """
    主程序入口，加载图数据，处理 function_id 信息，并保存结果。
    """
    parser = argparse.ArgumentParser(description="Add function_id to each identifier node in the graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    input_path = os.path.join(results_dir, 'defid_graph.json')
    output_path = os.path.join(results_dir, 'funcid_graph.json')

    graph = load_graph(input_path)
    if graph is None:
        return

    add_function_id_to_nodes(graph)
    save_graph(graph, output_path)
    os.remove(input_path)

if __name__ == "__main__":
    main()
