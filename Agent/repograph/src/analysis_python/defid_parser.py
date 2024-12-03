import networkx as nx
import json
import logging
from tqdm import tqdm  # 引入 tqdm 进度条库
import sys
import os
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为 INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)  # 创建日志记录器

# 全局缓存字典
file_id_cache = {}  # 缓存 file_id
file_tree_cache = {}  # 缓存每个文件的 identifier 节点


def build_file_id_cache(graph):
    """
    遍历所有节点，构建 file_id_cache，快速定位文件路径对应的 file_id。
    """
    for node_id, node_data in graph.nodes(data=True):
        if node_data.get("type") == "file" and "path" in node_data:
            file_path = node_data["path"]
            file_id_cache[file_path] = node_id  # 将路径映射到 file_id
            logger.debug(f"缓存文件路径: {file_path} -> {node_id}")

def build_file_tree_cache(graph):
    """
    遍历每个文件节点，递归查找文件中所有的 identifier 节点，构建 file_tree_cache。
    """
    # 遍历所有文件节点，构建缓存
    for file_id, file_path in tqdm(file_id_cache.items(), desc="构建文件树缓存"):
        file_tree_cache[file_id] = []  # 初始化缓存，存储该文件下的所有 identifier 节点
        find_identifiers_for_file(graph, file_id)  # 递归查找并填充缓存

def find_identifiers_for_file(graph, file_id):
    """
    递归遍历文件节点的子树，查找所有的 identifier 节点，并存入 file_tree_cache。
    """
    if file_id not in file_tree_cache:
        file_tree_cache[file_id] = []

    file_node = graph.nodes[file_id]
    children_ids = file_node.get("children", [])
    
    for child_id in children_ids:
        find_identifier_in_subtree(graph, child_id, file_id)

def find_identifier_in_subtree(graph, node_id, file_id):
    """
    在给定文件节点的子树中递归查找 identifier 节点，并将其添加到 file_tree_cache。
    """
    node_data = graph.nodes[node_id]
    
    # 如果是 identifier 节点，保存它
    if node_data.get("type") == "identifier":
        file_tree_cache[file_id].append(node_id)

    # 递归查找子节点
    children_ids = node_data.get("children", [])
    for child_id in children_ids:
        find_identifier_in_subtree(graph, child_id, file_id)
        
        
def find_definition_node(graph, definition):
    """
    根据 definition 信息找到对应的定义节点。
    """
    uri = definition["uri"].replace("file://", "")  # 转换 URI 为文件路径
    start_line = definition["range"]["start"]["line"]
    start_char = definition["range"]["start"]["character"]
    end_line = definition["range"]["end"]["line"]
    end_char = definition["range"]["end"]["character"]

    file_id = find_file_id_by_uri(graph, uri)
    if file_id is None:
        logger.debug(f"未找到与 URI 匹配的文件: {uri}")
        return None

    return find_node_in_file(graph, file_id, start_line, start_char, end_line, end_char)

def find_file_id_by_uri(graph, uri):
    """
    根据 URI 在图中找到对应的文件节点 ID (file_id)，并缓存结果以提高性能。
    """
    # 如果缓存中已经有这个 URI 的对应 ID，直接返回
    if uri in file_id_cache:
        return file_id_cache[uri]

    # 遍历图找到匹配的文件节点，并缓存结果
    for node_id, node_data in graph.nodes(data=True):
        if node_data.get("type") == "file" and node_data.get("path") == uri:
            file_id_cache[uri] = node_id  # 缓存文件 ID
            return node_id 

    # 未找到文件节点，返回 None
    return None

def find_node_in_file(graph, file_id, start_line, start_char, end_line, end_char):
    """
    查找文件节点中符合条件的 identifier 节点。
    """
    # 检查文件节点缓存
    if file_id in file_tree_cache:
        # 如果缓存中有这个文件的标识符节点，直接查找
        return find_identifier_from_cache(graph,file_tree_cache[file_id], start_line, start_char, end_line, end_char)

    file_tree_cache[file_id] = []
    # 如果缓存中没有，开始递归查找
    file_node = graph.nodes[file_id]
    children_ids = file_node.get("children", [])
    identifiers = []

    # 递归查找子树中的 identifier 节点
    for child_id in children_ids:
        result = find_identifier_in_subtree(graph, child_id, start_line, start_char, end_line, end_char,identifiers)
        file_tree_cache[file_id] +=identifiers
        if result:
            return result

    return None

def find_identifier_in_subtree(graph, node_id, start_line, start_char, end_line, end_char,identifiers):
    """
    递归地在子树中查找类型为 identifier 且位置匹配的节点。
    """
    node_data = graph.nodes[node_id]

    # 如果节点类型是 identifier，检查它的位置是否匹配
    if node_data.get("type") == "identifier":
        identifiers.append(node_id)
        start_point = node_data.get("sp", [None, None])
        end_point = node_data.get("ep", [None, None])

        if (start_point[0] == start_line and start_point[1] == start_char
                and end_point[0] == end_line and end_point[1] == end_char):
            return node_id  # 找到匹配的 identifier 节点

    # 递归地检查子节点
    children_ids = node_data.get("children", [])
    for child_id in children_ids:
        result = find_identifier_in_subtree(graph, child_id, start_line, start_char, end_line, end_char,identifiers)
        if result:
            return result  # 找到匹配节点后立即返回其 ID

    return None  # 未找到匹配的节点

def find_identifier_from_cache(graph,identifiers, start_line, start_char, end_line, end_char):
    """
    从缓存的标识符节点列表中查找符合位置条件的节点。
    """
    for identifier in identifiers:
        node_data = graph.nodes[identifier]
        start_point = node_data.get("sp", [None, None])
        end_point = node_data.get("ep", [None, None])

        if (start_point[0] == start_line and start_point[1] == start_char
                and end_point[0] == end_line and end_point[1] == end_char):
            return identifier  # 找到匹配的节点，返回其 ID
    
    return None  # 未找到匹配的节点

def add_definition_id_to_nodes(graph):
    """
    在每个有 definition 信息的节点上添加 defid 字段。
    """
    nodes = list(graph.nodes(data=True))  # 将节点转为列表
    for node_id, node_data in tqdm(nodes, desc="Processing Nodes"):  # 使用 tqdm 进度条
        if node_data["type"] in ['identifier'] and node_data.get("field_name") in ['function', 'attribute']:
            definition = node_data.get("definition",[])
            if len(definition) != 0:
                definition = node_data["definition"][0]  # 获取第一个定义信息
                def_node_id = find_definition_node(graph, definition)
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
    主程序入口，加载图数据，处理 definition 信息，并保存结果。
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

    add_definition_id_to_nodes(graph)
    save_graph(graph, output_path)
    os.remove(input_path)

if __name__ == "__main__":
    main()
