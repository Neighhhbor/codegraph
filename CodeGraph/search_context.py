import os
import networkx as nx
from code_graph import CodeGraph
from parsers.import_parser import ImportParser
from parsers.contains_parser import ContainsParser
from parsers.call_parser import CallParser
import config

def get_code_context(graph, target_node):
    """
    获取目标节点所在文件的上文和下文内容，和文件引入的模块。
    """
    # 获取目标节点的属性（比如它是 class、function 或者 method）
    target_data = graph.nodes[target_node]
    target_type = target_data['type']
    
    # 向上搜索，找到父节点为 module 的文件节点
    current_node = target_node
    while True:
        predecessors = list(graph.predecessors(current_node))
        if not predecessors:
            break  # 没有父节点了，说明到了根节点
        current_node = predecessors[0]
        if graph.nodes[current_node]['type'] == 'module':  # 找到文件节点
            target_file = current_node
            break
    else:
        target_file = None

    if not target_file:
        raise ValueError(f"无法找到 {target_node} 的模块文件节点")

    # 初始化结果字典
    result = {
        'target': target_node,
        'type': target_type,
        'file': target_file,
        'upward_context': [],
        'downward_context': [],
        'imports': []
    }

    # 获取在同一文件内的节点
    same_file_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') in ['class', 'function'] and n.startswith(target_file)]

    # 找到目标节点在文件中的位置
    if target_node in same_file_nodes:
        target_index = same_file_nodes.index(target_node)
    else:
        raise ValueError(f"找不到目标节点 {target_node} 在文件 {target_file} 中")

    # 获取上文内容（向上查找）
    for i in range(target_index - 1, -1, -1):
        node = same_file_nodes[i]
        node_type = graph.nodes[node]['type']
        if node_type in ['class', 'function']:  # 只考虑类、函数
            result['upward_context'].append(node)

    # 获取下文内容（向下查找）
    for i in range(target_index + 1, len(same_file_nodes)):
        node = same_file_nodes[i]
        node_type = graph.nodes[node]['type']
        if node_type in ['class', 'function']:  # 只考虑类、函数
            result['downward_context'].append(node)

    # 获取文件的 import 模块
    import_parser = ImportParser(os.path.join(config.PROJECT_PATH, target_file), target_file)
    import_parser.parse()

    # 只获取同 repo 下的模块
    repo_imports = [imp for imp in import_parser.imports if config.PROJECT_PATH in imp[1]]
    result['imports'] = repo_imports

    return result


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

    # 随机选择一个目标节点进行上下文分析
    target_node = 'stellar.stellar.app.Stellar.delete_orphan_snapshots'  # 假设这个是我们要查找的节点
    context_info = get_code_context(code_graph.get_graph(), target_node)

    # 打印目标节点的上下文
    print("Target node:", context_info['target'])
    print("Type:", context_info['type'])
    print("File:", context_info['file'])
    print("Upward Context:", context_info['upward_context'])
    print("Downward Context:", context_info['downward_context'])
    print("Imports:", context_info['imports'])


if __name__ == "__main__":
    main()
