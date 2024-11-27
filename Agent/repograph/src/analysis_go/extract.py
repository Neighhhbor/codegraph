import networkx as nx
import json
import logging
import os
import argparse
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# 定义保留的节点类型
RETAINED_TYPES = {"directory", "file"}
DEFINITION_TYPES = {"function_declaration" ,"var_declaration" , "method_declaration" }
IDENTIFIER_TYPES = {"identifier" , "field_identifier"}
VALID_TYPES = RETAINED_TYPES | DEFINITION_TYPES

# 定义自动生成文件的后缀
AUTO_GENERATED_SUFFIXES = ["pb.go"]
IGNORE_GRPC = True

def extract_skeleton(graph):
    """
    提取骨架图，保留目录、文件、类和方法节点，并将源代码添加到节点属性中。
    """
    skeleton = nx.DiGraph()

    # 遍历所有节点，提取源代码并加入节点属性
    for node_id, node_data in graph.nodes(data=True):
        node_type = node_data.get("type")
        
        if node_type in VALID_TYPES:
            # 保留需要的字段
            if node_type in DEFINITION_TYPES:
                # 仅保留 id, file_id, 和 code 字段
                file_id = node_data.get("file_id")
                file_path = None
                if file_id:
                    file_node = graph.nodes.get(file_id)
                    if file_node:
                        file_path = file_node.get("path")
                
                # 检查文件路径是否包含自动生成的后缀
                is_ignored = any(file_path.endswith(suffix) for suffix in AUTO_GENERATED_SUFFIXES) if file_path else False
                node_data["ignored"] = is_ignored  # 添加 ignored 标签

                # 提取该节点对应的源代码文本
                code = ""
                if file_path:
                    code = _get_node_text(node_data, file_path)  # 提取代码的函数
                
                # 在节点数据中加入 code 字段和 path
                node_data["code"] = code
                node_data["path"] = file_path
                node_data = {key: node_data[key] for key in ["id", "file_id", "code", "type", "path", "ignored"] if key in node_data}
            else:
                # 对于其他类型的节点（如 directory, file），保留原始数据并检查是否自动生成
                file_path = node_data.get("path")
                is_ignored = any(file_path.endswith(suffix) for suffix in AUTO_GENERATED_SUFFIXES) if file_path else False
                node_data["ignored"] = is_ignored  # 添加 ignored 标签
                if node_type == "file": 
                    if file_path:
                        with open(file_path, "r") as f:
                            code = f.read()
                        node_data["code"] = code
            # 将节点添加到骨架图    
            if IGNORE_GRPC and node_data["ignored"]:
                continue
            skeleton.add_node(node_id, **node_data)
    
    # 构建骨架图中的 contains 层级关系
    add_valid_edges(graph, skeleton)

    # 合并 program 到 file 节点
    merge_program_into_file(graph, skeleton)
    
    # 将 identifier 子节点通过 CONTAINS 关系加入到 class 或 method 节点中
    # add_identifier_to_skeleton(graph, skeleton)
    
    # # 将 identifier 子节点的 CALLS 关系移到 class 或 method 节点
    # move_identifier_calls_to_parent(graph, skeleton)

    return skeleton


def _get_node_text(node_data, file_path):
    """
    提取 AST 节点对应的源代码文本，使用字节位置信息来提取。
    :param node_data: 当前节点的数据
    :param file_path: 当前文件路径
    :return: 提取的代码文本
    """
    if node_data is None:
        return ""

    # 直接使用 start_byte 和 end_byte 提取代码片段
    start_byte = node_data.get("start_byte")
    end_byte = node_data.get("end_byte")

    if start_byte is None or end_byte is None:
        return ""

    with open(file_path, "rb") as file:
        file_content = file.read()

    # 返回文件中从 start_byte 到 end_byte 的代码片段
    return file_content[start_byte:end_byte].decode('utf-8')


def add_valid_edges(graph, skeleton):
    """
    为骨架图中保留的节点建立直接的 CONTAINS 层级关系。
    使用单源最短路径优化复杂度。
    """
    # 创建节点列表副本，避免迭代期间的结构修改
    skeleton_nodes = list(skeleton.nodes())
    
    for source in skeleton_nodes:
        # 获取从 source 到所有节点的最短路径
        all_paths = nx.single_source_shortest_path(graph, source)
        
        for target, path in all_paths.items():
            if source != target and target in skeleton_nodes:
                # 验证路径上的每一段边是否符合要求
                is_contains_path = True
                logger.debug(f"检查路径: {source} -> {target}: {path}")

                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    edge_data = graph.get_edge_data(u, v)
                    
                    # 检查是否存在 CONTAINS 类型的边
                    if not any(data.get("relationship") == "CONTAINS" for data in edge_data.values()):
                        is_contains_path = False
                        logger.debug(f"边 {u} -> {v} 不是 CONTAINS 类型。")
                        break
                    
                    # 检查中间节点是否是骨架节点
                    if u in skeleton_nodes and u != source and u != target:
                        is_contains_path = False
                        logger.debug(f"中间节点 {u} 是骨架节点，路径不符合条件。")
                        break
                
                # 如果路径符合条件，添加 CONTAINS 边
                if is_contains_path:
                    skeleton.add_edge(source, target, relationship="CONTAINS")
                    logger.debug(f"添加 CONTAINS 边: {source} -> {target}")

def merge_program_into_file(graph, skeleton):
    """
    将 program 节点的关系合并到其 file 节点，并移除 program 节点。
    """
    for node_id, node_data in list(skeleton.nodes(data=True)):
        if node_data["type"] == "program":
            # 使用 file_id 字段找到 program 节点的 file 父节点
            parent_id = node_data.get("file_id")
            if parent_id and skeleton.nodes.get(parent_id, {}).get("type") == "file":
                # 将 program 节点的出边迁移到 file 节点
                for _, target, edge_data in list(skeleton.out_edges(node_id, data=True)):
                    if not skeleton.has_edge(parent_id, target):
                        skeleton.add_edge(parent_id, target, **edge_data)
                    logger.debug(f"迁移边: {node_id} -> {target} 到 {parent_id} -> {target}")

                # 将 program 节点的入边迁移到 file 节点
                for source, _, edge_data in list(skeleton.in_edges(node_id, data=True)):
                    if not skeleton.has_edge(source, parent_id):
                        skeleton.add_edge(source, parent_id, **edge_data)
                    logger.debug(f"迁移边: {source} -> {node_id} 到 {source} -> {parent_id}")

                # 删除 program 节点
                skeleton.remove_node(node_id)
                logger.debug(f"删除 program 节点: {node_id}")

def move_identifier_calls_to_parent(graph, skeleton):
    """
    将 class 和 method 的 identifier 子节点上的 CALLS 关系移到对应的 class 或 method 节点上。
    """
    for node_id, node_data in graph.nodes(data=True):
        # 找到 class_declaration 和 method_declaration 节点
        if node_data["type"] in DEFINITION_TYPES:
            parent_node_id = node_id

            # 寻找该节点的 identifier 子节点
            for child_id in node_data.get("children", []):
                child_data = graph.nodes.get(child_id)
                if child_data and child_data["type"] in IDENTIFIER_TYPES and child_data.get("field_name") == "name":
                    
                    # 获取 identifier 节点的所有 CALLS 出边
                    for target_id, edge_data in graph[child_id].items():
                        for edge_key, edge_attrs in edge_data.items():
                            if edge_attrs.get("relationship") == "CALLS":
                                callee_id = edge_attrs.get("target")
                                # 确认被调用者在骨架图中
                                if parent_node_id in skeleton and callee_id in skeleton:
                                    # 添加 CALLS 边到骨架图中的父节点
                                    skeleton.add_edge(parent_node_id, callee_id, relationship="CALLS")
                                    logger.debug(f"添加 CALLS 关系: {parent_node_id} -> {callee_id}")

def add_identifier_to_skeleton(graph, skeleton):
    """
    将每个 class 或 method 的 identifier 子节点通过 CONTAINS 关系添加到骨架图。
    """
    for node_id, node_data in graph.nodes(data=True):
        # 找到 class_declaration 和 method_declaration 节点
        if node_data["type"] in  DEFINITION_TYPES:
            parent_node_id = node_id

            # 寻找该节点的 identifier 子节点
            for child_id in node_data.get("children", []):
                child_data = graph.nodes.get(child_id)
                if child_data and child_data["type"] in IDENTIFIER_TYPES and child_data.get("field_name") == "name":
                    # 创建不包含 `definition` 字段的副本
                    identifier_data = {k: v for k, v in child_data.items() if k != "definition"}
                    
                    # 添加 identifier 节点到骨架图中
                    skeleton.add_node(child_id, **identifier_data)
                    # 建立 CONTAINS 关系
                    skeleton.add_edge(parent_node_id, child_id, relationship="CONTAINS")
                    logger.debug(f"添加 CONTAINS 关系: {parent_node_id} -> {child_id}")

def transfer_calls_relationships_to_skeleton(graph, skeleton):
    """
    从原图中提取 CALLS 关系，并将这些关系转移到骨架图中的 method 或 class 节点上。
    """
    # 遍历原图中的所有边
    #进度条
    total_edges = len(graph.edges())
    with tqdm(total=total_edges, desc="转移 CALLS 关系", unit="edge") as pbar:
        for source_id, target_data in graph.adjacency():
            for target_id, edge_data in target_data.items():
                # 遍历每条边，检查是否是 CALLS 关系
                for edge_key, edge_attrs in edge_data.items():
                    if edge_attrs.get("relationship") == "CALLS":
                        # 获取 source 和 target 的父节点（method 或 class）
                        source_parent = get_parent_node(skeleton, source_id)
                        target_parent = get_parent_node(skeleton, target_id)
                        
                        if source_parent and target_parent:
                            # 将 CALLS 关系添加到骨架图中
                            if not skeleton.has_edge(source_parent, target_parent):
                                skeleton.add_edge(source_parent, target_parent, relationship="CALLS")
                                logger.debug(f"转移 CALLS 关系: {source_parent} -> {target_parent}")
            pbar.update(1)
            
def get_parent_node(skeleton, node_id):
    """
    根据 contains 关系获取节点的父节点，父节点为 method 或 class。
    """
    #检查是否在图中
    if node_id not in skeleton or skeleton.nodes[node_id] is None:
        logger.warning(f"节点 {node_id} 不在骨架图中")
        return None
    if skeleton.nodes[node_id].get("type", None) in DEFINITION_TYPES:
        return node_id
    for predecessor in skeleton.predecessors(node_id):
        if skeleton.nodes[predecessor]["type"] in DEFINITION_TYPES:
            return predecessor
    return None

def remove_identifiers_from_skeleton(skeleton):
    """
    删除骨架图中的所有 identifier 节点及其相关边。
    """
    identifiers_to_remove = [node_id for node_id, node_data in skeleton.nodes(data=True) if node_data.get("type", None) in IDENTIFIER_TYPES]
    # 把identifer 的 code 作为 父节点 name
    for identifier_id in identifiers_to_remove:
        node_data = skeleton.nodes.get(identifier_id)
        file_id = node_data.get("file_id")
        if file_id:
            file_node = skeleton.nodes.get(file_id)
            if file_node:
                file_path = file_node.get("path")
        # 提取该节点对应的源代码文本
        code = ""
        if file_path:
                code = _get_node_text(node_data, file_path)  # 你提到的提取代码的函数
        parent_id = node_data.get("parent")
        if parent_id:
            parent_node = skeleton.nodes.get(parent_id)
            if parent_node:
                parent_node["name"] = code
    skeleton.remove_nodes_from(identifiers_to_remove)
    logger.debug(f"删除了 {len(identifiers_to_remove)} 个 identifier 节点和相关的边")

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

def save_graph(graph, output_path):
    """
    将处理后的图保存为 JSON 文件。
    """
    try:
        data = nx.node_link_data(graph)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"子图已保存到: {output_path}")
    except Exception as e:
        logger.error(f"保存图时出错: {e}")

#遍历节点 把 path 改成相对 repo_path 的路径
def change_path_to_relative(graph, repo_path):
    for node_id, node_data in graph.nodes(data=True):
        if node_data.get("path"):
            node_data["path"] = os.path.relpath(node_data["path"], repo_path)

def main():
    """
    主程序入口，加载图数据，提取子图，并保存结果。
    """
    parser = argparse.ArgumentParser(description="提取并简化子图")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    input_path = os.path.join(results_dir, 'relation_graph.json')
    output_path = os.path.join(results_dir, 'subgraph.json')

    graph = load_graph(input_path)
    if graph is None:
        return

    # 提取骨架图
    skeleton = extract_skeleton(graph)

    # 转移原图中的 CALLS 关系到骨架图中的方法和类节点
    transfer_calls_relationships_to_skeleton(graph, skeleton)

    # # 删除骨架图中的 identifier 节点和相关边
    # remove_identifiers_from_skeleton(skeleton)
    change_path_to_relative(skeleton, repo_path)
    # 保存最终的子图    
    save_graph(skeleton, output_path)

if __name__ == "__main__":
    main()
