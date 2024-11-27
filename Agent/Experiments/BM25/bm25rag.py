import os
import json
from tqdm import tqdm
from rank_bm25 import BM25Okapi
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 定义路径
TEST_DATA_PATH = '/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_merged.jsonl'
FUNCTIONS_DIR = '/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/EmbeddingRAG/repocode'
OUTPUT_FILE = "./bm25_retrieved.jsonl"
TOP_K = 5  # 检索的 top-k 数量
MAX_WORKERS = 8  # 线程数量，可根据系统资源调整

# 创建锁
file_lock = threading.Lock()  # 锁用于确保文件写入的线程安全
processed_lock = threading.Lock()  # 锁用于确保处理过的 ids 更新线程安全

# 缓存函数库
function_cache = {}
class_cache = {}
method_cache = {}
batch_cache = []

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
        elif filename.endswith('_classes.json'):
            file_path = os.path.join(functions_dir, filename)
            base_name = filename.split('_')[0]  # 假设文件命名格式为 base_name_classes.json
            class_data = []
            with open(file_path, 'r') as f:
                for line in f:
                    class_data.append(json.loads(line))
            class_cache[base_name] = class_data  # 将该文件数据缓存
        elif filename.endswith('_methods.json'):
            file_path = os.path.join(functions_dir, filename)
            base_name = filename.split('_')[0]  # 假设文件命名格式为 base_name_methods.json
            method_data = []
            with open(file_path, 'r') as f:
                for line in f:
                    method_data.append(json.loads(line))
            method_cache[base_name] = method_data  # 将该文件数据缓存
    

# 构建 BM25 索引
def build_bm25_index(function_data):
    corpus = [func['code'].split() for func in function_data]
    bm25 = BM25Okapi(corpus)
    return bm25

# BM25 检索函数
def bm25_search(bm25, query, function_data, top_k=TOP_K):
    query_terms = query.split()
    scores = bm25.get_scores(query_terms)  # 获取所有文档的得分
    ranked_docs = sorted(
        zip(function_data, scores), key=lambda x: x[1], reverse=True
    )  # 按得分排序文档
    return ranked_docs[:top_k]  # 返回 top_k 的文档及其分数

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
    # 读取 processed_ids 时不需要加锁，读取操作本身是线程安全的
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
        "inputcode": test_item['input_code'],
        "signature": test_item['function_name'],
        "description": test_item['requirement'],
        "retrieved": [
            {
                "method": "bm25",
                "similar_code": doc['code'],
                "similar_signature": doc['name'],
                "file_path": doc['path'],
                "bm25_score": score  # 添加 BM25 分数
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
        # 清空缓存
        batch_cache.clear()

# 处理单条测试数据
def process_single_test_item(bm25, function_data, test_item, processed_ids):
    if already_processed(test_item, processed_ids):
        return None

    query = test_item['input_code']
    retrieved_docs = bm25_search(bm25, query, function_data, top_k=TOP_K)
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

            # 构建 BM25 索引并提交任务
            bm25 = build_bm25_index(function_data)
            futures.append(
                executor.submit(process_single_test_item, bm25, function_data, item, processed_ids)
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

    print(f"BM25 检索结果已保存到 '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()
