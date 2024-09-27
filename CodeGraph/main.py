import os
from code_graph import CodeGraph
from neo4j_utils import Neo4jHandler
from parsers.contains_parser import ContainsParser  # 引入包含关系的解析器
from parsers.import_parser import ImportParser  # 引入 import 关系的解析器
from parsers.call_parser import CallParser  # 引入调用关系的解析器
from lsp_client import LspClientWrapper  # LSP 客户端包装器
import config
import logging

RESULTDIR = "results"
# 全局日志配置
logging.basicConfig(level=logging.INFO, format=' %(name)s - %(levelname)s - %(message)s')

def main():
    # 连接到 Neo4j 数据库
    # neo4j_handler = Neo4jHandler(config.NEO4J_URL, config.NEO4J_USER, config.NEO4J_PASSWORD)
    
    # # 清空 Neo4j 数据库
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

    # 第三步：解析调用关系并启动 LSP 服务器
    lsp_client = LspClientWrapper(config.PROJECT_PATH)  # 初始化 LSP 客户端包装器
    lsp_client.start_server()  # 手动启动 LSP 服务器

    try:
        call_parser = CallParser(config.PROJECT_PATH, repo_name, code_graph, contains_parser.defined_symbols, lsp_client)
        call_parser.parse()  # 使用已解析的符号来处理调用关系

        # 输出已定义的符号（调试用）
        print('-'*50+'\n',f"已定义的符号: {call_parser.defined_symbols}\n",'-'*50+'\n')

        # 处理调用关系
        for caller, callee in call_parser.calls:
            code_graph.add_call(caller, callee)

    finally:
        lsp_client.stop_server()  # 手动停止 LSP 服务器

    # 保存代码图
    code_graph.export_to_gml(f"{RESULTDIR}/code_graph.gml")
    # 最后，将图导入到 Neo4j 数据库
    # neo4j_handler.import_graph(code_graph)

if __name__ == "__main__":
    main()
