import os
import json
import socket
import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from scipy.spatial.distance import cosine
import logging

# 定义路径
TEST_DATA_PATH = '/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_merged.jsonl'
FUNCTIONS_DIR = '/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/EmbeddingRAG/repocode'
OUTPUT_FILE = "./embedding_retrieved.jsonl"
TOP_K = 5  # 检索的 top-k 数量
MAX_WORKERS = 8  # 线程数量，可根据系统资源调整
MODEL_SERVER_PORT = 5000  # 嵌入模型服务端口

# 创建锁
file_lock = threading.Lock()  # 锁用于确保文件写入的线程安全
processed_lock = threading.Lock()  # 锁用于确保处理过的 ids 更新线程安全

# 缓存函数库
function_cache = {}
batch_cache = []
embedding_cache = {}

# 加载测试数据
def load_test_data(test_data_path):
    with open(test_data_path, 'r') as f:
        return [json.loads(line) for line in tqdm(f, desc="加载测试数据")]

# 加载所有函数库数据到缓存中
def load_all_function_data(functions_dir):
    for filename in tqdm(os.listdir(functions_dir), desc="加载所有函数库文件"):
        if filename.endswith('_functions.json'):
            file_path = os.path.join(functions_dir, filename)
            base_name = filename.split('_')[0]  # 假设文件命名格式为 base_name_functions.json
            function_data = []
            with open(file_path, 'r') as f:
                for line in f:
                    function_data.append(json.loads(line))
            function_cache[base_name] = function_data  # 将该文件数据缓存

# 连接到嵌入模型服务并请求嵌入
def get_embedding_from_server(text):
    """通过 Socket 向嵌入模型服务请求嵌入"""
    if text in embedding_cache:
        return embedding_cache[text]  # 如果嵌入已缓存，直接返回缓存的结果
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(('localhost', MODEL_SERVER_PORT))  # 确保连接到正确的端口
        send_all(s, f"embed:{text}")
        
        # 接收数据并验证大小
        result = receive_all(s)
        
        # 打印接收到的数据，检查其格式
        print("Received data from server:", result[:20])  # 打印前200个字符来检查数据内容

        try:
            # 
            data_len = len(result)
            element_size = np.dtype(np.float32).itemsize
            if data_len % element_size != 0:
                raise ValueError(f"Received data size {data_len} is not a multiple of element size {element_size}")

            # 将字节数据转换为 np.float32 数组
            embedding = np.frombuffer(result, dtype=np.float32)
            
            # 缓存嵌入结果
            embedding_cache[text] = embedding
            return embedding

        except Exception as e:
            print(f"Error processing embedding: {e}")
            return None



def send_all(conn, data, end_marker=b"<END>"):
    """完整发送数据，确保所有数据发送出去"""
    if isinstance(data, str):
        data = data.encode()  # 将字符串转换为字节类型
    data += end_marker
    total_sent = 0
    while total_sent < len(data):
        sent = conn.send(data[total_sent:])
        if sent == 0:
            raise RuntimeError("Socket connection broken")
        total_sent += sent

def receive_all(conn, buffer_size=4096):
    """完整接收数据，直到检测到 <END> 标记"""
    data = []
    while True:
        part = conn.recv(buffer_size)
        if not part:
            break
        data.append(part)
        if b"<END>" in part:
            break
    # 直接返回接收到的字节流，不进行解码
    full_data = b''.join(data).replace(b"<END>", b"")
    logging.info(f"Data received: (total length: {len(full_data)})")
    return full_data



# 计算相似度并返回最相关的 top_k 文档
def compute_similarity(query_embedding, function_data, top_k=TOP_K):
    """计算输入嵌入与所有函数的嵌入的余弦相似度"""
    similarities = []
    for func in function_data:
        func_embedding = get_embedding_from_server(func['code'])
        similarity = 1 - cosine(query_embedding, func_embedding)  # 余弦相似度，越接近 1 越相似
        similarities.append((func, similarity))
    similarities.sort(key=lambda x: x[1], reverse=True)  # 按相似度排序
    return similarities[:top_k]

# 过滤相似代码
def filter_similar_functions(retrieved_docs, test_item):
    project_path = test_item['project_path']
    function_name = test_item['function_name']
    return [
        (doc, score) for doc, score in retrieved_docs
        if doc['path'] != project_path or doc['name'] != function_name
    ]

# 检查是否已经存在于输出文件
def already_processed(test_item, processed_ids):
    return test_item['namespace'] in processed_ids

# 加载已处理条目
def load_processed_ids(output_file):
    processed_ids = set()
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in tqdm(f, desc="加载已处理条目"):
                entry = json.loads(line)
                processed_ids.add(entry['namespace'])
    return processed_ids

# 保存单条结果到 JSONL 文件
def save_result_to_jsonl(test_item, retrieved, output_file):
    entry = {
        "namespace": test_item['namespace'],
        "project_path": test_item['project_path'],
        "inputcode": test_item['input_code'],
        "signature": test_item['function_name'],
        "description": test_item['requirement'],
        "retrieved": [
            {
                "method": "embedding_rag",
                "similar_code": doc['code'],
                "similar_signature": doc['name'],
                "file_path": doc['path'],
                "similarity_score": score  # 添加相似度分数
            }
            for doc, score in retrieved
        ]
    }
    
    # 缓存结果
    batch_cache.append(entry)

    # 批量写入文件
    if len(batch_cache) >= 100:  # 每100条数据批量写入一次
        with file_lock:
            with open(output_file, 'a') as f:
                for item in batch_cache:
                    f.write(json.dumps(item) + "\n")
        batch_cache.clear()

# 处理单条测试数据
def process_single_test_item(function_data, test_item, processed_ids):
    if already_processed(test_item, processed_ids):
        return None

    query = test_item['input_code']
    query_embedding = get_embedding_from_server(query)  # 获取输入代码的嵌入
    retrieved_docs = compute_similarity(query_embedding, function_data, top_k=TOP_K)
    filtered_results = filter_similar_functions(retrieved_docs, test_item)
    return test_item, filtered_results

# 主流程
def main():
    # 1. 加载测试数据
    test_data = load_test_data(TEST_DATA_PATH)

    # 2. 加载所有函数库数据到缓存
    load_all_function_data(FUNCTIONS_DIR)

    # 3. 加载已处理条目
    processed_ids = load_processed_ids(OUTPUT_FILE)

    # 4. 开始处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []

        # 使用 tqdm 为并行处理添加进度条
        for item in tqdm(test_data, desc="处理测试数据", position=0, leave=False):
            project_path = item['project_path']
            base_name = project_path.split('/')[1]  # 提取项目的基础名称

            # 从缓存中获取对应的函数库数据
            function_data = function_cache.get(base_name)
            if not function_data:  # 如果缓存中没有该数据，跳过该项
                continue

            futures.append(
                executor.submit(process_single_test_item, function_data, item, processed_ids)
            )

        # 等待所有任务完成
        for future in tqdm(as_completed(futures), total=len(futures), desc="处理检索结果"):
            result = future.result()
            if result is not None:
                test_item, filtered_results = result
                save_result_to_jsonl(test_item, filtered_results, OUTPUT_FILE)
                # 更新已处理条目
                with processed_lock:
                    processed_ids.add(test_item['namespace'])

    # 在主线程中写入剩余数据
    if batch_cache:
        with file_lock:
            with open(OUTPUT_FILE, 'a') as f:
                for item in batch_cache:
                    f.write(json.dumps(item) + "\n")
        batch_cache.clear()

if __name__ == "__main__":
    main()
