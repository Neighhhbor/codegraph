from code_graph import CodeGraph
from neo4j_utils import Neo4jHandler
from code_parser import CodeParser
import config

def main():
    neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    neo4j_handler.clean_database()

    parser = CodeParser(config.PROJECT_PATH)
    parser.parse()

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

    neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
