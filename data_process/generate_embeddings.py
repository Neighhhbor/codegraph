import os
import sys
import json
import logging
import networkx as nx
import numpy as np
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import socket

# 设置路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from Agent.tools.model_server import start_model_server, stop_model_server, MODEL_SERVER_PORT

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GRAPHS_DIR = "./graphs"
EMBEDDINGS_DIR = "./embeddings"
MAX_WORKERS = 12  # 根据您的系统资源调整

# 维护一个字典来跟踪已生成的嵌入
generated_embeddings = {}

def get_embedding(text):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', MODEL_SERVER_PORT))
            s.sendall(f"embed:{text}".encode())
            response = s.recv(4096)  # 假设嵌入向量不会超过4096字节
            return np.frombuffer(response, dtype=np.float32)
    except Exception as e:
        logging.error(f"获取嵌入向量时出错: {e}")
        return None

def process_graph(graph_file):
    graph_path = os.path.join(GRAPHS_DIR, graph_file)
    base_name = os.path.splitext(graph_file)[0]
    embeddings_path = os.path.join(EMBEDDINGS_DIR, f"{base_name}_embeddings.npz")

    # 检查是否已经生成过嵌入
    if os.path.exists(embeddings_path):
        logging.info(f"嵌入文件已存在，跳过处理: {embeddings_path}")
        return

    logging.info(f"处理图文件: {graph_file}")

    # 加载图
    with open(graph_path, 'r') as f:
        graph_data = json.load(f)
    graph = nx.node_link_graph(graph_data)

    # 获取所有函数节点
    function_nodes = [(n, d) for n, d in graph.nodes(data=True) if d.get('type') == 'function']

    embeddings = {}
    for node, data in tqdm(function_nodes, desc=f"生成 {base_name} 的嵌入"):
        code = data.get('code', '')
        if code in generated_embeddings:
            embedding = generated_embeddings[code]
        else:
            embedding = get_embedding(code)
            if embedding is not None:
                generated_embeddings[code] = embedding
        
        if embedding is not None:
            embeddings[node] = embedding

    # 保存嵌入
    np.savez(embeddings_path, **embeddings)
    logging.info(f"嵌入已保存到: {embeddings_path}")

def generate_all_embeddings():
    # 确保输出目录存在
    os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

    # 获取所有图文件
    graph_files = [f for f in os.listdir(GRAPHS_DIR) if f.endswith('.json')]

    # 启动模型服务器
    start_model_server()

    try:
        # 使用进程池并发处理
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_graph, graph_file) for graph_file in graph_files]

            for future in tqdm(as_completed(futures), total=len(graph_files), desc="处理图文件"):
                try:
                    future.result()
                except Exception as exc:
                    logging.error(f"处理图文件时发生错误: {exc}")
    finally:
        # 停止模型服务器
        stop_model_server()

if __name__ == "__main__":
    generate_all_embeddings()
