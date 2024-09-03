import os
from code_graph import CodeGraph
from neo4j_utils import Neo4jHandler
from contains_parser import ContainsParser  # 引入包含关系的解析器
from import_parser import ImportParser  # 引入import关系的解析器
from call_parser import CallParser  # 引入调用关系的解析器
import config

def main():
    # 连接到 Neo4j 数据库
    neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    # 清空 Neo4j 数据库
    neo4j_handler.clean_database()

    # 获取项目名称
    repo_name = os.path.basename(os.path.normpath(config.PROJECT_PATH))

    # 第一步：解析CONTAINS关系
    contains_parser = ContainsParser(config.PROJECT_PATH, repo_name)
    contains_parser.parse()

    # 构建代码图
    code_graph = CodeGraph()

    # 遍历树形结构并构建图，从根节点开始
    code_graph.build_graph_from_tree(contains_parser.root)

    # 第二步：解析import关系
    import_parser = ImportParser(config.PROJECT_PATH, repo_name)
    import_parser.parse()

    # 处理import关系
    for importer, imported_module in import_parser.imports:
        print(f"importer: {importer}, imported_module: {imported_module}")
        code_graph.add_import(importer, imported_module)

    # 第三步：解析调用关系
    call_parser = CallParser(config.PROJECT_PATH, repo_name, code_graph)
    call_parser.parse()

    # 处理调用关系
    for caller, callee in call_parser.calls:
        code_graph.add_call(caller, callee)

    # 最后，将图导入到 Neo4j 数据库
    neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
