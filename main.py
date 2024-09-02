import os
from code_graph import CodeGraph
from neo4j_utils import Neo4jHandler
from code_parser import CodeParser
import config

def main():
    neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    neo4j_handler.clean_database()

    repo_name = os.path.basename(os.path.normpath(config.PROJECT_PATH))
    parser = CodeParser(config.PROJECT_PATH, repo_name)
    parser.parse()

    code_graph = CodeGraph()

    # 遍历每个文件的树形结构并构建图
    for tree in parser.trees.values():
        code_graph.build_graph_from_tree(tree)

    # 处理调用关系
    # for caller, callee in parser.calls:
    #     code_graph.add_call(caller, callee)

    neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
