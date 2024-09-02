import os
from code_graph import CodeGraph
from neo4j_utils import Neo4jHandler
from contains_parser import ContainsParser  # 引入包含关系的解析器
from call_import_parser import CallAndImportParser  # 引入调用和导入关系的解析器
import config

def main():
    neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    neo4j_handler.clean_database()

    repo_name = os.path.basename(os.path.normpath(config.PROJECT_PATH))

    # 第一步：解析CONTAINS关系
    contains_parser = ContainsParser(config.PROJECT_PATH, repo_name)
    contains_parser.parse()

    code_graph = CodeGraph()

    # 遍历每个文件的树形结构并构建图
    for tree in contains_parser.trees.values():
        code_graph.build_graph_from_tree(tree)

    # 第二步：解析调用关系和import关系
    call_import_parser = CallAndImportParser(config.PROJECT_PATH, repo_name)
    call_import_parser.parse()

    # 处理调用关系
    for caller, callee in call_import_parser.calls:
        code_graph.add_call(caller, callee)

    neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
