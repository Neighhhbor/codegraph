import networkx as nx
import json
import logging
from tqdm import tqdm
import sys
import argparse
import os
import cProfile
import pstats
import io

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为 INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# 全局缓存
file_id_cache = {}
identifier_by_file = {}

def preprocess_graph(graph):
    """
    预处理图，建立 file_id 到 uri 的映射，并按 file_id 分组存储 identifier 节点。
    """
    logger.info("开始预处理图...")
    for node_id, node_data in tqdm(graph.nodes(data=True), desc="Preprocessing Nodes"):
        node_type = node_data.get("type")
        if node_type == "file":
            uri = node_data.get("path")
            if uri:
                file_id_cache[uri] = node_id
        elif node_type == "identifier":
            file_id = node_data.get("file_id")
            
            if file_id:
                if file_id not in identifier_by_file:
                    identifier_by_file[file_id] = []
                identifier_by_file[file_id].append((node_id, node_data))
    logger.info("预处理完成。")

def find_definition_node_optimized(definition):
    """
    根据 definition 信息找到对应的定义节点，使用预处理后的 identifier_by_file 进行快速查找。
    """
    uri = definition["uri"].replace("file://", "")
    start_line = definition["range"]["start"]["line"]
    start_char = definition["range"]["start"]["character"]
    end_line = definition["range"]["end"]["line"]
    end_char = definition["range"]["end"]["character"]

    file_id = file_id_cache.get(uri)
    if file_id is None:
        logger.debug(f"未找到与 URI 匹配的文件: {uri}")
        return None

    # 从预处理的 identifier 列表中查找匹配的节点
    identifier_list = identifier_by_file.get(file_id, [])
    for node_id, node_data in identifier_list:
        sp = node_data.get("sp", [None, None])
        ep = node_data.get("ep", [None, None])
        if (sp[0] == start_line and sp[1] == start_char and
            ep[0] == end_line and ep[1] == end_char):
            print(node_data)
            return node_id
    return None

def add_definition_id_to_nodes_optimized(graph):
    """
    在每个有 definition 信息的节点上添加 defid 字段，使用优化后的查找方法。
    """
    nodes = list(graph.nodes(data=True))
    for node_id, node_data in tqdm(nodes, desc="Adding defid to Nodes"):
        if "definition" in node_data and len(node_data["definition"]) > 0:
            definition = node_data["definition"][0]
            def_node_id = find_definition_node_optimized(definition)
            if def_node_id:
                node_data["defid"] = def_node_id
                logger.debug(f"节点 {node_id} 的定义节点 ID 为 {def_node_id}")
            else:
                logger.debug(f"未找到定义节点: {definition['uri']}")

def load_graph(input_path):
    """
    从 JSON 文件加载图数据。
    """
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
        graph = nx.node_link_graph(data)
        logger.debug(f"成功加载图: {input_path}")
        return graph
    except FileNotFoundError:
        logger.debug(f"未找到图文件: {input_path}")
        return None
    except Exception as e:
        logger.debug(f"加载图时出错: {e}")
        return None

def save_graph(graph, output_path):
    """
    将处理后的图保存为 JSON 文件。
    """
    try:
        data = nx.node_link_data(graph)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.debug(f"图已成功保存到: {output_path}")
    except Exception as e:
        logger.debug(f"保存图时出错: {e}")

def main():
    """
    主程序入口，加载图数据，预处理，处理 definition 信息，并保存结果。
    """
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    input_path = os.path.join(results_dir, 'definitiongraph.json')
    output_path = os.path.join(results_dir, 'defid_graph.json')

    graph = load_graph(input_path)
    if graph is None:
        return

    preprocess_graph(graph)  # 预处理图
    add_definition_id_to_nodes_optimized(graph)  # 添加 defid 字段
    save_graph(graph, output_path)

def profile_code():
    # 创建一个 cProfile 运行器
    pr = cProfile.Profile()
    pr.enable()  # 开始性能分析

    main()  # 运行你要分析的主程序

    pr.disable()  # 停止性能分析

    # 将性能分析结果打印到控制台
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')  # 按累计时间排序
    ps.print_stats()
    print(s.getvalue())

if __name__ == "__main__":
    profile_code()
