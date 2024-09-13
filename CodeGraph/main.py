import os
import matplotlib.pyplot as plt
import networkx as nx
from code_graph import CodeGraph
# from neo4j_utils import Neo4jHandler  # 引入 Neo4j 的工具类，注释掉
from parsers.contains_parser import ContainsParser  # 引入包含关系的解析器
from parsers.import_parser import ImportParser  # 引入 import 关系的解析器
from parsers.call_parser import CallParser  # 引入调用关系的解析器
from semantic_analyzer import SemanticAnalyzer  # 引入语义分析器
from save_similarity_data import save_similarity_to_csv, save_similarity_to_json  # 保存相似度数据的函数
import config
import logging
import matplotlib
matplotlib.use('Agg')  # 设置非交互式后端

# 设置可见的 GPU 设备
os.environ['CUDA_VISIBLE_DEVICES'] = '7'

# 全局日志配置
logging.basicConfig(level=logging.INFO, format=' %(name)s - %(levelname)s - %(message)s')

def visualize_similar_subgraph(graph):
    """
    可视化仅包含SIMILAR关系的子图，并将其保存为文件
    """
    # Extract SIMILAR relationships from the graph
    similar_edges = [(u, v) for u, v, d in graph.edges(data=True) if d.get('relationship') == 'SIMILAR']
    
    # Create a subgraph containing only the nodes and SIMILAR edges
    similar_subgraph = graph.edge_subgraph(similar_edges).copy()
    
    # Visualize the subgraph
    out_put_path = os.path.join("../data_process/similarity", "similar_subgraph_visualization.png")
    plt.figure(figsize=(12, 12))
    pos = nx.spring_layout(similar_subgraph, k=0.5)  # 布局图形
    nx.draw(similar_subgraph, pos, with_labels=True, node_size=3000, font_size=10, node_color="lightgreen", font_weight="bold")
    plt.title("Similar Subgraph Visualization")
    plt.savefig(out_put_path)
    print("Similar subgraph visualization saved to 'similar_subgraph_visualization.png'")
    plt.close()  # 关闭图像，释放资源

def print_adjacency_list(graph):
    """
    输出图的邻接表
    """
    adj_list = nx.generate_adjlist(graph)
    for line in adj_list:
        print(line)

def main():
    # 连接到 Neo4j 数据库，注释掉数据库连接部分
    # neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    # 清空 Neo4j 数据库，注释掉数据库清理部分
    # neo4j_handler.clean_database()

    # 获取项目名称
    repo_name = os.path.basename(os.path.normpath(config.PROJECT_PATH))

    # 第一步：解析 CONTAINS 关系
    contains_parser = ContainsParser(config.PROJECT_PATH, repo_name)
    contains_parser.parse()  # 解析目录结构和类、函数定义

    # 构建代码图
    code_graph = CodeGraph()

    # 遍历树形结构并构建图，从根节点开始
    code_graph.build_graph_from_tree(contains_parser.root)

    # 第二步：解析 import 关系
    import_parser = ImportParser(config.PROJECT_PATH, repo_name)
    import_parser.parse()
    print(f"import_parser.imports: {import_parser.imports}")
    # 处理 import 关系
    for import_data in import_parser.imports:
        importer = import_data[0]
        imported_module = import_data[1]
        print(f"importer: {importer}, imported_module: {imported_module}")
        code_graph.add_import(importer, imported_module)

    # 第三步：解析调用关系
    call_parser = CallParser(config.PROJECT_PATH, repo_name, code_graph, contains_parser.defined_symbols)
    call_parser.parse()  # 使用已解析的符号来处理调用关系

    # 输出已定义的符号（调试用）
    print('-'*50+'\n',f"已定义的符号: {call_parser.defined_symbols}\n",'-'*50+'\n')

    # 处理调用关系
    for caller, callee in call_parser.calls:
        code_graph.add_call(caller, callee)

    # 第四步：进行语义相似性分析，并创建SIMILAR关系的边
    semantic_analyzer = SemanticAnalyzer()  # 实例化语义分析器
    similar_pairs, similarities = semantic_analyzer.find_similar_nodes(code_graph)  # 查找相似节点对并返回相似度

    # 保存相似度数据为 CSV 和 JSON
    save_similarity_to_csv(similar_pairs, similarities, filename="similarity_data.csv")
    save_similarity_to_json(similar_pairs, similarities, filename="similarity_data.json")

    # 为相似的节点对创建SIMILAR关系的边
    for node1, node2 in similar_pairs:
        code_graph.add_similarity_edge(node1, node2)

    # 可视化仅包含 SIMILAR 关系的子图并保存到文件
    visualize_similar_subgraph(code_graph.get_graph())

    # 打印图的邻接表
    # print("Adjacency List of the Code Graph:")
    # print_adjacency_list(code_graph.get_graph())

    # 最后，将图导入到 Neo4j 数据库（暂时注释掉）
    # neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
