import igraph as ig
import matplotlib.pyplot as plt
from tqdm import tqdm
import json
import os

RESULTDIR = "results"
ALGORITHMS = ["Infomap", "Leiden", "Louvain", "Label Propagation", "Walktrap"]

def load_graph_from_json(filename):
    """从 JSON 文件加载图"""
    with open(filename, 'r') as infile:
        graph_data = json.load(infile)

    # 从 JSON 数据创建 igraph 图
    vertices = [v['id'] for v in graph_data['nodes']]
    edges = [(link['source'], link['target']) for link in graph_data['links']]

    # 构建 directed 图 (有向图)
    ig_G = ig.Graph(directed=True)
    ig_G.add_vertices(vertices)
    ig_G.add_edges(edges)

    # 将节点的属性从 JSON 文件中添加到 igraph 节点中
    for v in graph_data['nodes']:
        for key, value in v.items():
            if key != 'id':  # 'id' 已作为顶点名称使用
                ig_G.vs.find(name=v['id'])[key] = value

    return ig_G

def apply_community_detection(algorithm_name, ig_G):
    """根据算法名称应用社区检测"""
    if algorithm_name == "Infomap":
        partition = ig_G.community_infomap()
    elif algorithm_name == "Leiden":
        import leidenalg as la
        partition = la.find_partition(ig_G, la.ModularityVertexPartition)
    elif algorithm_name == "Louvain":
        import leidenalg as la
        partition = la.find_partition(ig_G, la.RBConfigurationVertexPartition)
    elif algorithm_name == "Label Propagation":
        partition = ig_G.community_label_propagation()
    elif algorithm_name == "Walktrap":
        partition = ig_G.community_walktrap().as_clustering()
    else:
        raise ValueError(f"Unknown algorithm: {algorithm_name}")

    return partition

def export_community_info(partition, ig_G, output_filename):
    """导出社区信息到 JSON 文件"""
    community_info = {}
    for community_id in set(partition.membership):
        community_info[community_id] = {
            "nodes": []
        }

        # Use tqdm to show the progress of node processing
        for vertex_id in tqdm(range(len(partition.membership)), desc=f"Processing community {community_id}"):
            if partition.membership[vertex_id] == community_id:
                node_info = {
                    "id": ig_G.vs[vertex_id].index,
                    "attributes": {}
                }

                # 获取所有属性
                for attr in ig_G.vs[vertex_id].attributes():
                    node_info["attributes"][attr] = ig_G.vs[vertex_id][attr]

                community_info[community_id]["nodes"].append(node_info)

    with open(output_filename, 'w') as outfile:
        json.dump(community_info, outfile, indent=4)

def analyze_communities(graph_filename, algorithm_name):
    """执行指定算法的社区分析并导出结果"""
    try:
        ig_G = load_graph_from_json(graph_filename)
        partition = apply_community_detection(algorithm_name, ig_G)

        print(f"Using {algorithm_name}:")
        print(f"Community Count: {len(set(partition.membership))}")
        print(f"Modularity: {partition.modularity if hasattr(partition, 'modularity') else 'N/A'}")

        # 导出社区信息到 JSON
        output_filename = os.path.join(RESULTDIR, f"community_info_{algorithm_name.lower()}.json")
        export_community_info(partition, ig_G, output_filename)
        print(f"Exported community info to {output_filename}")

    except Exception as e:
        print(f"Error during analysis with {algorithm_name}: {e}")

if __name__ == "__main__":
    # Define the directory and file paths
    graph_json_path = os.path.join(RESULTDIR, "OpenHands.json")

    # Ensure the results directory exists
    if not os.path.exists(RESULTDIR):
        os.makedirs(RESULTDIR)

    # Analyze communities using each algorithm
    for algorithm_name in ALGORITHMS:
        analyze_communities(graph_json_path, algorithm_name)
