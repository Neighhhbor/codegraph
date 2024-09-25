import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
from tqdm import tqdm

import json
import os

RESULTDIR = "results"
def load_graph_from_gml(filename):
    """从 GML 文件加载图"""
    return ig.Graph.Read_GML(filename)

def plot_communities(partition, ig_G):
    """绘制社区检测图并保存为 PNG 文件"""
    community_colors = partition.membership
    num_communities = max(community_colors) + 1

    palette = plt.get_cmap("tab10", num_communities)
    vertex_colors = [palette(color) for color in community_colors]

    layout = ig_G.layout("fr")
    fig, ax = plt.subplots(figsize=(10, 8))
    ig.plot(ig_G, layout=layout, vertex_color=vertex_colors, vertex_size=20, vertex_label=None, target=ax)

    plt.title("Community Detection using Leiden Algorithm")
    plt.savefig(os.path.join(RESULTDIR, "community_detection.png"))
    plt.show()


def export_community_info(partition, ig_G, output_filename):
    """导出社区信息到 JSON 文件"""
    community_info = {}
    for community_id in set(partition.membership):
        community_info[community_id] = {
            "nodes": []
        }
        
        # 使用 tqdm 显示进度条
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
    ig_G = load_graph_from_gml(graph_filename)
    partition = la.find_partition(ig_G, la.ModularityVertexPartition)

    print(f"社区数量: {len(partition)}")
    print(f"模块度: {partition.modularity}")

    plot_communities(partition, ig_G)
    export_community_info(partition, ig_G, os.path.join(RESULTDIR, "community_info.json"))

if __name__ == "__main__":
    analyze_communities(f"{RESULTDIR}/code_graph.gml")
