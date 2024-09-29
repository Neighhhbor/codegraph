import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
from tqdm import tqdm
import json
import os

RESULTDIR = "results"

def load_graph_from_json(filename):
    """从 NetworkX 导出的 JSON 文件加载图"""
    with open(filename, 'r') as infile:
        graph_data = json.load(infile)

    # 从 NetworkX 的 JSON 格式手动创建 igraph 图
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

def plot_communities(partition, ig_G):
    """绘制社区检测图并保存为 PNG 文件"""
    community_colors = partition.membership
    num_communities = max(community_colors) + 1

    # Create color palette
    palette = plt.get_cmap("tab10", num_communities)
    vertex_colors = [palette(color) for color in community_colors]

    # Use 'fr' layout for plotting
    layout = ig_G.layout("fr")
    fig, ax = plt.subplots(figsize=(10, 8))
    ig.plot(ig_G, layout=layout, vertex_color=vertex_colors, vertex_size=20, vertex_label=None, target=ax)

    plt.title("Community Detection using Leiden Algorithm")
    plt.savefig(os.path.join(RESULTDIR, "community_detection.png"))
    # plt.show()

def plot_each_community_separately(partition, ig_G):
    """为每个社区生成单独的图像"""
    num_communities = max(partition.membership) + 1

    for community_id in set(partition.membership):
        subgraph = ig_G.subgraph([v for v, mem in enumerate(partition.membership) if mem == community_id])
        layout = subgraph.layout("fr")

        fig, ax = plt.subplots(figsize=(8, 6))
        ig.plot(subgraph, layout=layout, vertex_size=20, vertex_label=None, target=ax)

        plt.title(f"Community {community_id}")
        plt.savefig(os.path.join(RESULTDIR, f"community_{community_id}.png"))
        # plt.show()

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

def analyze_communities(graph_filename):
    """执行社区分析并绘图"""
    try:
        ig_G = load_graph_from_json(graph_filename)
        partition = la.find_partition(ig_G, la.ModularityVertexPartition)

        print(f"社区数量: {len(partition)}")
        print(f"模块度: {partition.modularity}")

        # 绘制并导出社区图
        plot_communities(partition, ig_G)

        # 为每个社区单独绘图
        plot_each_community_separately(partition, ig_G)

        # 导出社区信息到 JSON
        export_community_info(partition, ig_G, os.path.join(RESULTDIR, "community_info_autogen.json"))

    except Exception as e:
        print(f"分析社区时出现错误: {e}")

if __name__ == "__main__":
    # Define the directory and file paths
    graph_json_path = os.path.join(RESULTDIR, "autogen.json")

    # Analyze communities on the loaded JSON graph
    analyze_communities(graph_json_path)
