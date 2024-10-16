import streamlit as st
import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
from tqdm import tqdm
import json
import os
from pyvis.network import Network
import streamlit.components.v1 as components
import metis  # 导入 METIS 库

# 设置页面为宽屏布局
st.set_page_config(layout="wide")

RESULTDIR = "results"

def load_graph_from_json(filename):
    """从 JSON 文件加载图"""
    with open(filename, 'r') as infile:
        graph_data = json.load(infile)

    vertices = [v['id'] if 'id' in v else f"node_{i}" for i, v in enumerate(graph_data['nodes'])]
    edges = [(link['source'], link['target']) for link in graph_data['links']]

    ig_G = ig.Graph(directed=True)
    ig_G.add_vertices(vertices)
    ig_G.add_edges(edges)
    
    for i, v in enumerate(graph_data['nodes']):
        for key, value in v.items():
            if key != 'id':
                ig_G.vs[i][key] = value

    return ig_G

def apply_community_detection(algorithm_name, ig_G):
    """应用选择的社区检测算法"""
    if algorithm_name == "Leiden":
        partition = la.find_partition(ig_G, la.ModularityVertexPartition)
    elif algorithm_name == "Louvain":
        partition = la.find_partition(ig_G, la.RBConfigurationVertexPartition)
    elif algorithm_name == "Label Propagation":
        partition = ig_G.community_label_propagation()
    elif algorithm_name == "Walktrap":
        partition = ig_G.community_walktrap().as_clustering()
    elif algorithm_name == "Infomap":
        partition = ig_G.community_infomap()
    elif algorithm_name == "Multilevel (METIS)":
        partition = apply_multilevel_partitioning(ig_G)
    else:
        st.error(f"Unknown algorithm: {algorithm_name}")
        return None

    return partition

def apply_multilevel_partitioning(ig_G):
    """使用 METIS 进行多级划分"""
    # 将 igraph 图转换为 NetworkX 图
    import networkx as nx
    G_nx = nx.Graph()

    for vertex in ig_G.vs:
        G_nx.add_node(vertex.index, **vertex.attributes())

    for edge in ig_G.es:
        source, target = edge.source, edge.target
        G_nx.add_edge(source, target, weight=edge["weight"] if "weight" in edge.attributes() else 1)

    # 使用 METIS 进行划分，划分为 4 个部分（可根据需要调整）
    edgecuts, parts = metis.part_graph(G_nx, nparts=4)
    
    # 将 METIS 的划分结果转换为 igraph 的格式
    membership = parts
    num_communities = max(membership) + 1

    # 创建伪分区对象，兼容 igraph 分区结构
    class PseudoPartition:
        def __init__(self, membership):
            self.membership = membership
            self.num_communities = len(set(membership))
        
        @property
        def modularity(self):
            # 计算模块度（简单计算）
            return ig_G.modularity(membership)

    return PseudoPartition(membership)

def plot_community(community_id, partition, ig_G):
    """绘制单个社区并显示"""
    community_nodes = [i for i, membership in enumerate(partition.membership) if membership == community_id]
    subgraph = ig_G.subgraph(community_nodes)
    layout = subgraph.layout("fr")
    fig, ax = plt.subplots(figsize=(12, 8))

    vertex_labels = subgraph.vs['id'] if 'id' in subgraph.vs.attributes() else [str(i) for i in range(subgraph.vcount())]
    ig.plot(subgraph, layout=layout, vertex_label=vertex_labels, vertex_size=20, target=ax)

    plt.title(f"Community {community_id} Structure")
    st.pyplot(fig)

def display_community_info(community_id, partition, ig_G):
    """显示社区中的所有节点及其属性"""
    community_nodes = [i for i, membership in enumerate(partition.membership) if membership == community_id]
    st.write(f"### Community {community_id} Nodes and Attributes")

    for node_id in community_nodes:
        node = ig_G.vs[node_id]
        node_name = node['name'] if 'name' in node.attributes() else f"node_{node_id}"
        st.write(f"{node_name}")

        if 'code' in node.attributes() and node['code'] is not None:
            with st.expander(f"Code", expanded=False):
                formatted_code = node['code'].replace('\\n', '\n').replace('\\t', '\t')
                st.code(formatted_code, language="python")
        else:
            st.write("         ")

def plot_interactive_communities(ig_G, partition):
    """使用 Pyvis 绘制交互式社区检测图"""
    net = Network(notebook=False, height="1000px", width="100%", bgcolor="#f0f0f0", font_color="black")
    community_colors = partition.membership
    num_communities = max(community_colors) + 1
    palette = plt.get_cmap("tab10", num_communities)
    
    for vertex_id in range(len(ig_G.vs)):
        node_name = ig_G.vs[vertex_id]['name'] if 'name' in ig_G.vs.attributes() else f"node_{vertex_id}"
        community_id = partition.membership[vertex_id]
        color = palette(community_id)
        color_hex = f'#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}'
        
        net.add_node(vertex_id, label=node_name, title=node_name, color=color_hex, size=30)
    
    for edge in ig_G.es:
        source = edge.source
        target = edge.target
        relationship = edge['relationship'] if 'relationship' in edge.attributes() else "None"
        net.add_edge(source, target, title=f"{relationship}", width=2)

    options = {
        "nodes": {"borderWidth": 2, "size": 16},
        "edges": {"color": {"color": "gray"}, "smooth": {"enabled": False}},
        "interaction": {"navigationButtons": True, "keyboard": True},
        "physics": {
            "enabled": True,
            "barnesHut": {"gravitationalConstant": -15000, "centralGravity": 0.1, "springLength": 800, "springConstant": 0.02, "damping": 0.09, "avoidOverlap": 1},
            "minVelocity": 0.75,
            "solver": "barnesHut",
            "timestep": 0.4,
            "adaptiveTimestep": True
        }
    }

    net.set_options(json.dumps(options))
    path = "interactive_graph.html"
    net.write_html(path, open_browser=False, notebook=False)
    
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            components.html(html_content, height=1000)
    else:
        st.write("Failed to generate HTML file")

def analyze_communities(graph_filename, algorithm_name):
    """执行社区分析并显示社区数量和模块度"""
    ig_G = load_graph_from_json(graph_filename)
    partition = apply_community_detection(algorithm_name, ig_G)

    if partition is not None:
        st.session_state['ig_G'] = ig_G
        st.session_state['partition'] = partition
        st.session_state['algorithm_name'] = algorithm_name

        # 显示社区数量和模块度
        community_count = len(set(partition.membership))
        modularity_score = partition.modularity if hasattr(partition, 'modularity') else 'N/A'
        st.write(f"**Selected Algorithm:** {algorithm_name}")
        st.write(f"**Community Count:** {community_count}")
        st.write(f"**Modularity:** {modularity_score}")

        # 仅在用户选择社区时显示详细信息
        selected_community = st.selectbox("Select a community to view details", range(community_count))
        if selected_community is not None:
            display_community_info(selected_community, partition, ig_G)
            plot_community(selected_community, partition, ig_G)


def get_json_files(directory):
    """获取指定目录下的所有 JSON 文件"""
    return [f for f in os.listdir(directory) if f.endswith('.json')]

if __name__ == "__main__":
    st.title("社区检测分析")
    
    # 获取 results 目录下的所有 JSON 文件
    json_files = get_json_files(RESULTDIR)
    
    # 让用户选择要分析的文件
    selected_file = st.selectbox("选择要分析的图文件", json_files)
    
    graph_json_path = os.path.join(RESULTDIR, selected_file)
    
    algorithm_name = st.selectbox(
        "选择社区检测算法",
        ["Leiden", "Louvain", "Label Propagation", "Walktrap", "Infomap", "Multilevel (METIS)"]
    )

    if 'ig_G' not in st.session_state or st.session_state.get('algorithm_name') != algorithm_name or st.button("分析"):
        analyze_communities(graph_json_path, algorithm_name)
    else:
        ig_G = st.session_state['ig_G']
        partition = st.session_state['partition']
        st.write(f"社区数量: {len(set(partition.membership))}")
        st.write(f"模块度: {partition.modularity if hasattr(partition, 'modularity') else 'N/A'}")
        
        selected_community = st.selectbox("选择要查看详情的社区", range(len(set(partition.membership))))
        if selected_community is not None:
            display_community_info(selected_community, partition, ig_G)
            plot_community(selected_community, partition, ig_G)
