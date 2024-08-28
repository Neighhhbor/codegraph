from parser.code_parser import CodeParser
from graph.code_graph import CodeGraph
from graph.neo4j_utils import Neo4jHandler
import config

def main():
    # 初始化Neo4j处理器
    neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    # 清空数据库
    neo4j_handler.clean_database()

    # 解析代码库
    parser = CodeParser(config.PROJECT_PATH)
    parser.parse()

    # 构建关系图
    code_graph = CodeGraph()
    for file in parser.files:
        code_graph.add_file(file)
    for class_name, class_data in parser.classes.items():
        code_graph.add_class(class_name, class_data["file"])
    for func_name, func_data in parser.functions.items():
        container = func_data.get("class") or func_data["file"]
        code_graph.add_function(func_name, container)
    for caller, callee in parser.calls:
        code_graph.add_call(caller, callee)

    # 导入Neo4j数据库
    neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
