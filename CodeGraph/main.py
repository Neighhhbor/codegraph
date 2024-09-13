import os
import matplotlib.pyplot as plt
import networkx as nx
from code_graph import CodeGraph
# from neo4j_utils import Neo4jHandler  # 引入 Neo4j 的工具类，注释掉
from parsers.contains_parser import ContainsParser  # 引入包含关系的解析器
from parsers.import_parser import ImportParser  # 引入 import 关系的解析器
from parsers.call_parser import CallParser  # 引入调用关系的解析器
from semantic_analyzer import SemanticAnalyzer  # 引入语义分析器
import config
import logging

# 设置可见的 GPU 设备
os.environ['CUDA_VISIBLE_DEVICES'] = '7'

# 全局日志配置
logging.basicConfig(level=logging.INFO, format=' %(name)s - %(levelname)s - %(message)s')

def visualize_graph(graph):
    """
    可视化代码图
    """
    plt.figure(figsize=(12, 12))
    pos = nx.spring_layout(graph, k=0.5)  # 布局图形
    nx.draw(graph, pos, with_labels=True, node_size=3000, font_size=10, node_color="lightblue", font_weight="bold")
    plt.title("Code Graph Visualization")
    plt.show()

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
    similar_pairs = semantic_analyzer.find_similar_nodes(code_graph)  # 查找相似节点对

    # 为相似的节点对创建SIMILAR关系的边
    for node1, node2 in similar_pairs:
        code_graph.add_similarity_edge(node1, node2)

    # 可视化代码图
    visualize_graph(code_graph.get_graph())

    # 打印图的邻接表
    print("Adjacency List of the Code Graph:")
    print_adjacency_list(code_graph.get_graph())

    # 最后，将图导入到 Neo4j 数据库（暂时注释掉）
    # neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
