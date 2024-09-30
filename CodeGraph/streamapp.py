import streamlit as st
import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
from tqdm import tqdm
import json
import os

# 设置页面为宽屏布局
st.set_page_config(layout="wide")

RESULTDIR = "results"

def load_graph_from_json(filename):
    """从 NetworkX 导出的 JSON 文件加载图"""
    with open(filename, 'r') as infile:
        graph_data = json.load(infile)

    # 从 NetworkX 的 JSON 格式手动创建 igraph 图
    vertices = [v['id'] if 'id' in v else f"node_{i}" for i, v in enumerate(graph_data['nodes'])]  # 添加默认 ID
    edges = [(link['source'], link['target']) for link in graph_data['links']]

    # 构建 directed 图 (有向图)
    ig_G = ig.Graph(directed=True)
    ig_G.add_vertices(vertices)
    ig_G.add_edges(edges)
    
    # 将节点的属性从 JSON 文件中添加到 igraph 节点中
    for i, v in enumerate(graph_data['nodes']):
        for key, value in v.items():
            if key != 'id':  # 'id' 已作为顶点名称使用
                ig_G.vs[i][key] = value

    return ig_G

def plot_community(community_id, partition, ig_G):
    """绘制单个社区并显示"""
    community_nodes = [i for i, membership in enumerate(partition.membership) if membership == community_id]

    subgraph = ig_G.subgraph(community_nodes)

    layout = subgraph.layout("fr")
    fig, ax = plt.subplots(figsize=(12, 8))  # 调整为更大的尺寸
    ig.plot(subgraph, layout=layout, vertex_label=subgraph.vs['id'], vertex_size=20, target=ax)

    plt.title(f"Community {community_id} Structure")
    st.pyplot(fig)

def display_community_info(community_id, partition, ig_G):
    """显示社区中的所有节点及其属性"""
    community_nodes = [i for i, membership in enumerate(partition.membership) if membership == community_id]

    st.write(f"### Community {community_id} Nodes and Attributes")

    for node_id in community_nodes:
        node = ig_G.vs[node_id]
        node_id_value = node['id'] if 'id' in node.attributes() else f"node_{node_id}"
        
        # 检查是否有 namespace 属性
        namespace = node['id'] if 'namespace' in node.attributes() else 'No namespace'

        st.write(f"Node ID: {node_id_value}")
        st.write(f"Namespace: {namespace}")  # 显示 namespace
        
        # 如果节点有 code 属性，将其格式化显示为代码，并处理换行符
        if 'code' in node.attributes():
            formatted_code = node['code'].replace('\\n', '\n').replace('\\t', '\t')  # 确保换行符和缩进被正确解析
            st.code(formatted_code, language="python")  # 使用 st.code 显示代码并处理换行
        else:
            st.json({attr: node[attr] for attr in node.attributes()})

def plot_communities(partition, ig_G):
    """绘制社区检测图并保存为 PNG 文件"""
    community_colors = partition.membership
    num_communities = max(community_colors) + 1

    # Create color palette
    palette = plt.get_cmap("tab10", num_communities)
    vertex_colors = [palette(color) for color in community_colors]

    # Use 'fr' layout for plotting
    layout = ig_G.layout("fr")
    fig, ax = plt.subplots(figsize=(12, 8))  # 调整为更大的尺寸
    ig.plot(ig_G, layout=layout, vertex_color=vertex_colors, vertex_size=20, vertex_label=None, target=ax)

    plt.title("Community Detection using Leiden Algorithm")
    st.pyplot(fig)

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
    ig_G = load_graph_from_json(graph_filename)
    partition = la.find_partition(ig_G, la.ModularityVertexPartition)

    st.session_state['ig_G'] = ig_G
    st.session_state['partition'] = partition

    st.write(f"社区数量: {len(partition)}")
    st.write(f"模块度: {partition.modularity}")

    plot_communities(partition, ig_G)

    # 添加一个下拉选择框以选择要查看的社区
    selected_community = st.selectbox("Select a community to view details", range(len(set(partition.membership))))

    if selected_community is not None:
        # 显示所选社区的节点和属性
        display_community_info(selected_community, partition, ig_G)
        # 绘制所选社区的图结构
        plot_community(selected_community, partition, ig_G)

if __name__ == "__main__":
    # 设置 Streamlit 标题
    st.title("Community Detection Analysis")

    # 文件路径输入框
    graph_json_path = st.text_input("Enter the graph JSON file path", os.path.join(RESULTDIR, "autogen.json"))

    # 如果 session_state 中没有分析结果，执行分析，否则直接显示已分析数据
    if 'ig_G' not in st.session_state or st.button("Analyze"):
        analyze_communities(graph_json_path)
    else:
        ig_G = st.session_state['ig_G']
        partition = st.session_state['partition']
        
        st.write(f"社区数量: {len(partition)}")
        st.write(f"模块度: {partition.modularity}")

        # 添加一个下拉选择框以选择要查看的社区
        selected_community = st.selectbox("Select a community to view details", range(len(set(partition.membership))))

        if selected_community is not None:
            # 显示所选社区的节点和属性
            display_community_info(selected_community, partition, ig_G)
            # 绘制所选社区的图结构
            plot_community(selected_community, partition, ig_G)
