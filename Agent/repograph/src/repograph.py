import os
import json
import networkx as nx
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


GRAPH_DIR = "/home/shixianjie/codegraph/codegraph/Agent/repograph"


def load_graph(input_path):
    """
    从 JSON 文件加载图数据。
    """
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
        graph = nx.node_link_graph(data)
        logger.debug(f"成功加载图: {input_path}")
        return graph
    except FileNotFoundError:
        logger.debug(f"未找到图文件: {input_path}")
        return None
    except Exception as e:
        logger.debug(f"加载图时出错: {e}")
        return None


def get_caller_nodes_for_namespace(namespace: str) -> list:
    """
    根据给定的命名空间，找到对应的图，并返回所有 CALLS 关系中指向该命名空间的节点。
    
    :param namespace: 一个字符串，表示完整的命名空间（例如："stellar.func2"）。
    
    :return: 返回一个列表，包含所有指向给定命名空间的源节点的 ID。列表中的每个元素是一个字符串，表示源节点的 ID。
    
    :raises ValueError: 如果图数据库中没有找到对应的命名空间的图，抛出该异常。
    """
    reponame = namespace.split('.')[0]
    # graph_path = f'{reponame}.json'
    graph_path = '/home/shixianjie/codegraph/codegraph/Agent/repograph/src/stellar.json'
    if not os.path.exists(graph_path):
        raise ValueError(f"图数据库文件 {graph_path} 不存在")
    
    graph = load_graph(graph_path)    
     # 查找所有 CALLS 关系中指向给定命名空间的节点
    caller_nodes = []
    container_nodes = []
    for u, v, data in graph.edges(data=True):
        
        if data.get("relationship") == "CALLS":
            # 检查目标节点的命名空间是否与给定的命名空间匹
            if data.get('target_namespace') == namespace:
                caller_nodes.append(u)  # 将源节点添加到结果列表
        if data.get("relationship") == "CONTAINS":
            if data.get('target_namespace') == namespace:
                container_nodes.append(u)  # 将源节点添加到结果列表
    
    # 打印每个 caller 节点的信息
    for node in caller_nodes:
        node_data = graph.nodes[node]  # 获取节点的完整信息
        print_nodes(node_data)  # 以 JSON 格式打印节点数据

    # 打印每个 container 节点的信息
    for node in container_nodes:
        node_data = graph.nodes[node]  # 获取节点的完整信息
        print_nodes(node_data)  # 以 JSON 格式打印节点数据

    # 打印日志信息
    logger.debug(f"找到 {len(caller_nodes)} 个指向 {namespace} 的 CALLS 关系节点")
    logger.debug(f"找到 {len(container_nodes)} 个包含 {namespace} 的 CONTAINS 关系节点")
    return caller_nodes, container_nodes

def print_nodes(node_data):
    """
    格式化节点数据并以 JSON 格式打印出来
    :param node_data: 包含节点信息的字典
    """
    # 将节点信息以格式化的 JSON 输出
    node_data = { 
        "namespace": node_data.get('namespace', ''),
        "name": node_data.get('name', ''),
        "path": node_data.get('path', ''),
        "type": node_data.get('type', '').split('_')[0],
        "code": node_data.get('code', '')
    }
    print(json.dumps(node_data, indent=4, ensure_ascii=False))
    
if __name__ == "__main__":
    namespace = "stellar.stellar.app.Operations.__init__"
    caller_nodes, container_nodes = get_caller_nodes_for_namespace(namespace)

