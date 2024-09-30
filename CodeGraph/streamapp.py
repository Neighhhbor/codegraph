import streamlit as st
import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
from tqdm import tqdm
import json
import os
from pyvis.network import Network  # 增加 pyvis 导入
import shutil
# 设置页面为宽屏布局
st.set_page_config(layout="wide")

RESULTDIR = "results"

def load_graph_from_json(filename):
    """从 NetworkX 导出的 JSON 文件加载图"""
    with open(filename, 'r') as infile:
        graph_data = json.load(infile)

    # 从 JSON 文件中提取顶点和边信息
    vertices = [v['id'] if 'id' in v else f"node_{i}" for i, v in enumerate(graph_data['nodes'])]  # 使用 JSON 中的 'id' 字段作为顶点名称
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

    # 获取社区的子图
    subgraph = ig_G.subgraph(community_nodes)

    # 使用 'fr' 布局
    layout = subgraph.layout("fr")
    fig, ax = plt.subplots(figsize=(12, 8))  # 调整为更大的尺寸

    # 确认 'id' 属性是否存在，如果不存在则使用索引作为默认标签
    if 'id' in subgraph.vs.attributes():
        vertex_labels = subgraph.vs['id']
    else:
        vertex_labels = [str(i) for i in range(subgraph.vcount())]  # 使用索引作为标签

    # 绘制子图
    ig.plot(subgraph, layout=layout, vertex_label=vertex_labels, vertex_size=20, target=ax)

    plt.title(f"Community {community_id} Structure")
    st.pyplot(fig)


def display_community_info(community_id, partition, ig_G):
    """显示社区中的所有节点及其属性"""
    community_nodes = [i for i, membership in enumerate(partition.membership) if membership == community_id]

    st.write(f"### Community {community_id} Nodes and Attributes")

    for node_id in community_nodes:
        node = ig_G.vs[node_id]
        
        # 使用节点的 'name' 作为节点名称
        node_name = node['name'] if 'name' in node.attributes() else f"node_{node_id}"

        # 显示节点名称
        st.write(f"{node_name}")

        # 检查 code 属性是否为 None，并用 expander 折叠代码段
        if 'code' in node.attributes() and node['code'] is not None:
            with st.expander(f"Code for {node_name}", expanded=False):
                formatted_code = node['code'].replace('\\n', '\n').replace('\\t', '\t')  # 确保换行符和缩进被正确解析
                st.code(formatted_code, language="python")  # 使用 st.code 显示代码并处理换行
        else:
            st.write("No code available for this node.")
        
        # # 检查 signature 属性是否为 None
        # if 'signature' in node.attributes() and node['signature'] is not None:
        #     st.write(f"Signature: {node['signature']}")
        # else:
        #     st.write("No signature available for this node.")


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

import json
import streamlit.components.v1 as components
import os

def plot_interactive_communities(ig_G, partition):
    """使用 Pyvis 绘制交互式社区检测图（显示更大）"""
    # 设置图的宽度和高度为更大的尺寸
    net = Network(notebook=False, height="1000px", width="100%", bgcolor="#f0f0f0", font_color="black")

    # 获取社区的颜色（不同社区用不同颜色）
    community_colors = partition.membership
    num_communities = max(community_colors) + 1
    palette = plt.get_cmap("tab10", num_communities)
    
    for vertex_id in range(len(ig_G.vs)):
        node_name = ig_G.vs[vertex_id]['name'] if 'name' in ig_G.vs.attributes() else f"node_{vertex_id}"
        community_id = partition.membership[vertex_id]
        color = palette(community_id)  # 根据社区给节点上色
        color_hex = f'#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}'
        
        # 调整节点大小，使用 size 属性
        net.add_node(vertex_id, label=node_name, title=node_name, color=color_hex, size=30)  # 设置节点大小为 30
    
    # 添加边并显示属性
    for edge in ig_G.es:
        source = edge.source
        target = edge.target
        relationship = edge['relationship'] if 'relationship' in edge.attributes() else "None"  # 假设边有 weight 属性
        # 调整边的粗细，使用 width 属性，并显示边的属性
        net.add_edge(source, target, title=f"{relationship}", width=2)  # 边的宽度设置为 3

    # 设置物理引擎参数，适度保留交互性
    options = {
        "nodes": {
            "borderWidth": 2,
            "size": 16,
            "color": {
                "border": "black",
                "highlight": {
                    "border": "orange",
                    "background": "yellow"
                }
            },
            "font": {
                "size": 16
            }
        },
        "edges": {
            "color": {
                "color": "gray"
            },
            "smooth": {
                "enabled": False
            }
        },
        "interaction": {
            "navigationButtons": True,
            "keyboard": True
        },
        "physics": {
            "enabled": True,
            "barnesHut": {
                "gravitationalConstant": -15000,
                "centralGravity": 0.1,
                "springLength": 800,
                "springConstant": 0.02,
                "damping": 0.09,
                "avoidOverlap": 1
            },
            "minVelocity": 0.75,
            "solver": "barnesHut",
            "timestep": 0.4,
            "adaptiveTimestep": True
        }
    }

    # 将选项转换为 JSON 字符串
    net.set_options(json.dumps(options))

    # 生成交互式图的HTML内容
    path = "interactive_graph.html"
    net.write_html(path, open_browser=False, notebook=False)
    
    # 检查文件是否正确生成
    if os.path.exists(path):
        st.write("HTML 文件已生成")
    else:
        st.write("HTML 文件生成失败")

    # 读取HTML文件的内容并嵌入
    try:
        with open(path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            # 直接将HTML内容嵌入到Streamlit中
            components.html(html_content, height=1000)
    except Exception as e:
        st.write(f"加载 HTML 文件时出错: {e}")




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

    plot_interactive_communities(ig_G, partition)

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

        plot_interactive_communities(ig_G, partition)

        # 添加一个下拉选择框以选择要查看的社区
        selected_community = st.selectbox("Select a community to view details", range(len(set(partition.membership))))

        if selected_community is not None:
            # 显示所选社区的节点和属性
            display_community_info(selected_community, partition, ig_G)
            # 绘制所选社区的图结构
            plot_community(selected_community, partition, ig_G)
