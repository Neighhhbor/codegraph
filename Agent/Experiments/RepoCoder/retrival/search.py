import os
import json
import numpy as np
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.spatial.distance import cosine
import threading
from sentence_transformers import SentenceTransformer
import torch

os.environ["CUDA_VISIBLE_DEVICES"]="2,3"
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retrieval_process.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 路径和常量定义
TEST_DATA_PATH = 'metadata_rgrg.jsonl'
EMBEDDING_DIR = './embeddings'
REPOCODE_DIR = '/home/shixianjie/codegraph/codegraph/Agent/repocode'
OUTPUT_FILE = "./top10_retrieved_rgrg.jsonl"
TOP_K = 10  # 检索的 top-k 数量
MAX_WORKERS = 32  # 线程数量，可根据系统资源调整
BATCH_CACHE = []
MODEL_NAME = "dunzhang/stella_en_400M_v5"

# 创建锁
file_lock = threading.Lock()
processed_lock = threading.Lock()

# 初始化嵌入缓存
embedding_cache = {}


# 加载测试数据
def load_test_data(test_data_path):
    with open(test_data_path, 'r') as f:
        return [json.loads(line) for line in tqdm(f, desc="加载测试数据")]


# 加载特定项目的待检索函数嵌入和补充的代码信息
def load_embeddings_for_project(project_name):
    """
    加载指定项目的嵌入和代码信息，如果缺少 codes 和 paths 则从 repocode 补充加载
    :param project_name: 项目名称
    :return: 包含函数名、嵌入向量、代码和路径的字典
    """
    embedding_file = os.path.join(EMBEDDING_DIR, f"embeddings_{project_name}_functions.json")
    if not os.path.exists(embedding_file):
        logger.warning(f"Embedding file for project '{project_name}' not found.")
        return None

    with open(embedding_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 检查是否存在 codes 和 paths
    if 'codes' in data and 'paths' in data:
        logger.info(f"Loaded embeddings with codes and paths for project: {project_name}")
        return {
            "functions": data['functions'],
            "embeddings": [np.array(embedding, dtype=np.float32) for embedding in data['embeddings']],
            "codes": data['codes'],
            "paths": data['paths']
        }
    else:
        # 如果缺少 codes 和 paths，从 repocode 加载
        logger.info(f"Codes and paths missing in embeddings, loading from repocode for project: {project_name}")
        code_path_map = load_code_and_paths_from_repocode(project_name)
        return {
            "functions": data['functions'],
            "embeddings": [np.array(embedding, dtype=np.float32) for embedding in data['embeddings']],
            "codes": [code_path_map.get(func, {}).get('code', "Code unavailable") for func in data['functions']],
            "paths": [code_path_map.get(func, {}).get('path', "Path unavailable") for func in data['functions']]
        }


# 从 repocode 加载代码内容和路径
def load_code_and_paths_from_repocode(project_name):
    """
    从 repocode 目录加载指定项目的代码和路径
    :param project_name: 项目名称
    :return: {函数名: {code: 代码, path: 路径}} 的字典
    """
    project_file = os.path.join(REPOCODE_DIR, f"{project_name}_functions.json")
    code_path_map = {}
    if os.path.exists(project_file):
        logger.info(f"Loading code and paths from repocode for project: {project_name}")
        with open(project_file, 'r', encoding='utf-8') as f:
            for line in f:
                func_data = json.loads(line.strip())
                code_path_map[func_data['name']] = {
                    "code": func_data.get('code', "Code unavailable"),
                    "path": func_data.get('path', "Path unavailable")
                }
    else:
        logger.warning(f"Repocode file not found for project: {project_name}")
    return code_path_map


# 检索函数
def embedding_search(query_embedding, function_data, top_k=TOP_K):
    similarities = []
    for func_name, func_embedding, func_code, func_path in zip(
            function_data['functions'], function_data['embeddings'], function_data['codes'], function_data['paths']):
        similarity = 1 - cosine(query_embedding, func_embedding)
        similarities.append((func_name, func_code, func_path, similarity))
    similarities.sort(key=lambda x: x[3], reverse=True)
    return similarities[:top_k]

# 过滤相似代码
def filter_similar_functions(retrieved_docs, test_item):
    function_name = test_item['namespace']
    return [(doc_name, doc_code, doc_path, score) for doc_name, doc_code, doc_path, score in retrieved_docs if doc_name != function_name]


# 检查是否已经存在于输出文件
def already_processed(test_item, processed_ids):
    return test_item['namespace'] in processed_ids


# 加载已处理条目
def load_processed_ids(output_file):
    processed_ids = set()
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in tqdm(f, desc="加载已处理条目", position=0):
                entry = json.loads(line)
                processed_ids.add(entry['namespace'])
    return processed_ids


# 保存单条结果到 JSONL 文件
def save_result_to_jsonl(test_item, retrieved, output_file):
    entry = {
        "namespace": test_item['namespace'],
        "project_path": test_item['project_path'],
        "inputcode": test_item['completions'][0],
        "retrieved": [
            {
                "method": "embedding",
                "similar_code": doc_code,
                "similar_signature": doc_name,
                "file_path": doc_path,
                "similarity_score": score
            }
            for doc_name, doc_code, doc_path, score in retrieved
        ]
    }

    BATCH_CACHE.append(entry)

    if len(BATCH_CACHE) >= 100:
        with file_lock:
            with open(output_file, 'a') as f:
                for item in BATCH_CACHE:
                    f.write(json.dumps(item) + "\n")
        BATCH_CACHE.clear()


# 处理单条测试数据
def process_single_test_item(query_embedding, function_data, test_item, processed_ids):
    if already_processed(test_item, processed_ids):
        return None

    retrieved_docs = embedding_search(query_embedding, function_data, top_k=TOP_K)
    filtered_results = filter_similar_functions(retrieved_docs, test_item)
    return test_item, filtered_results


# 动态生成 input_code 的嵌入
def compute_input_code_embedding(model, input_code):
    return model.encode(input_code, convert_to_tensor=True).cpu().numpy()


# 主流程
def main():
    test_data = load_test_data(TEST_DATA_PATH)
    processed_ids = load_processed_ids(OUTPUT_FILE)

    # 初始化嵌入模型
    logger.info("加载嵌入模型...")
    
    model = SentenceTransformer(MODEL_NAME, trust_remote_code=True,device=device)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for item in tqdm(test_data, desc="处理测试数据", position=0, leave=False):
            namespace = item['namespace']
            input_code = item['completions'][0]  # 提取生成的代码
            query_embedding = compute_input_code_embedding(model, input_code)

            project_path = item['project_path']
            base_name = project_path.split('/')[1]
            function_data = embedding_cache.get(base_name)
            if function_data is None:
                function_data = load_embeddings_for_project(base_name)
                if function_data:
                    embedding_cache[base_name] = function_data
                else:
                    continue

            futures.append(executor.submit(process_single_test_item, query_embedding, function_data, item, processed_ids))

        for future in tqdm(as_completed(futures), total=len(futures), desc="处理检索结果"):
            result = future.result()
            if result is not None:
                test_item, filtered_results = result
                save_result_to_jsonl(test_item, filtered_results, OUTPUT_FILE)
                with processed_lock:
                    processed_ids.add(test_item['namespace'])

    if BATCH_CACHE:
        with file_lock:
            with open(OUTPUT_FILE, 'a') as f:
                for item in BATCH_CACHE:
                    f.write(json.dumps(item) + "\n")
        BATCH_CACHE.clear()

    logger.info(f"Embedding RAG 检索结果已保存到 '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
