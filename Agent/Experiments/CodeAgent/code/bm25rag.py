import os
import json
from tqdm import tqdm
from rank_bm25 import BM25Okapi
from concurrent.futures import ThreadPoolExecutor, as_completed
import tree_sitter_python as tsp
import threading
from tree_sitter import Language, Parser
from copy import deepcopy

# Tree-sitter setup
PY_LANGUAGE = Language(tsp.language())
parser = Parser()
parser.language = PY_LANGUAGE

# 定义路径
TEST_DATA_PATH = '/home/shixianjie/codegraph/codegraph/Agent/Experiments/promptelements/LM_prompt_elements_merged.jsonl'
FUNCTIONS_DIR = '/home/shixianjie/codegraph/codegraph/Agent/repocode'
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

# 替换目标函数体


def replace_function_body(tree, code, target_function_name):
    """
    只替换目标函数体（block），不影响其他函数。
    :param tree: Tree-sitter 解析后的语法树
    :param code: 原始 Python 代码字符串
    :param target_function_name: 需要替换函数体的目标函数名
    :return: 替换后的代码
    """
    cursor = tree.walk()  # 获取 AST 游标
    updated_code = code

    def visit_node(cursor):
        nonlocal updated_code

        # 如果节点是 'function_definition'
        if cursor.node.type == 'function_definition':

            function_id = cursor.node.child_by_field_name('name')
            function_name = function_id.text.decode('utf-8')

            # 仅替换目标函数的代码
            if function_name == target_function_name:
                # 找到函数体并替换
                # print(function_name, target_function_name)
                body_node = cursor.node.child_by_field_name('body')
                if body_node:
                    body_start_byte = body_node.start_byte
                    body_end_byte = cursor.node.end_byte
                    new_body = "<CODETOCOMPLETE>"

                    # 更新代码：替换函数体
                    updated_code = updated_code[:body_start_byte] + \
                        new_body + updated_code[body_end_byte:]

        # 递归处理子节点
        if cursor.goto_first_child():
            visit_node(cursor)
            cursor.goto_parent()  # 返回父节点

        # 递归处理兄弟节点
        while cursor.goto_next_sibling():
            visit_node(cursor)

    visit_node(cursor)  # 从根节点开始遍历

    return updated_code

# 加载测试数据


def load_test_data(test_data_path):
    with open(test_data_path, 'r') as f:
        return [json.loads(line) for line in tqdm(f, desc="加载测试数据")]

# 加载所有函数库数据到缓存中


def load_all_function_data(functions_dir):
    for filename in tqdm(os.listdir(functions_dir), desc="加载所有函数库文件"):
        if filename.endswith('_functions.json'):
            file_path = os.path.join(functions_dir, filename)
            base_name = filename.split('_')[0]
            function_data = []
            with open(file_path, 'r') as f:
                for line in f:
                    function_data.append(json.loads(line))
            function_cache[base_name] = function_data
        elif filename.endswith('_classes.json'):
            file_path = os.path.join(functions_dir, filename)
            base_name = filename.split('_')[0]
            class_data = []
            with open(file_path, 'r') as f:
                for line in f:
                    class_data.append(json.loads(line))
            class_cache[base_name] = class_data
        # elif filename.endswith('_methods.json'):
        #     file_path = os.path.join(functions_dir, filename)
        #     base_name = filename.split('_')[0]
        #     method_data = []
        #     with open(file_path, 'r') as f:
        #         for line in f:
        #             method_data.append(json.loads(line))
        #     method_cache[base_name] = method_data

# 构建 BM25 索引


def build_bm25_index(function_data, class_data, method_data):
    combined_data = function_data + class_data + method_data
    corpus = [item['code'].split() for item in combined_data]
    bm25 = BM25Okapi(corpus)
    return bm25, combined_data

# BM25 检索函数


def bm25_search(bm25, query, combined_data, top_k=TOP_K):
    query_terms = query.split()
    scores = bm25.get_scores(query_terms)
    ranked_docs = sorted(
        zip(combined_data, scores), key=lambda x: x[1], reverse=True
    )
    return ranked_docs[:top_k]

# 过滤相似代码


def filter_similar_functions(retrieved_docs, test_item):
    function_name = test_item['function_name']
    completion_path = test_item['completion_path']
    # print(function_name)
    filtered_docs = []
    for doc, score in retrieved_docs:
        doc_copy = deepcopy(doc)
        if doc_copy['path'] == completion_path:
            tree = parser.parse(bytes(doc_copy['code'], "utf8"))
            replaced_code = replace_function_body(tree, doc_copy['code'], function_name)
            doc_copy['code'] = replaced_code
        filtered_docs.append((doc_copy, score))

    return filtered_docs


# 检查是否已经存在于输出文件
def already_processed(test_item, processed_ids):
    # 读取 processed_ids 时不需要加锁，读取操作本身是线程安全的
    return test_item['namespace'] in processed_ids

# 加载已处理条目z


def load_processed_ids(output_file):
    processed_ids = set()
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in tqdm(f, desc="加载已处理条目", position=0):
                entry = json.loads(line)
                processed_ids.add(entry['namespace'])
    return processed_ids

# 保存单条结果到 JSONL 文件


# 保存单条结果到 JSONL 文件
def save_result_to_jsonl(test_item, retrieved, output_file):
    entry = {
        "namespace": test_item['namespace'],
        "project_path": test_item['project_path'],
        "inputcode": test_item['input_code'],
        "signature": test_item['function_name'],
        "completion_path": test_item['completion_path'],
        "description": test_item['requirement'],
        "retrieved": [
            {
                "method": "bm25",
                "similar_code": doc['code'],
                "similar_signature": doc['name'],
                "file_path": doc['path'],
                "bm25_score": score
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
                    f.write(json.dumps(item) + "\n")  # 省去 indent 参数，确保平铺
        # 清空缓存
        batch_cache.clear()

# 处理剩余的缓存数据
def flush_batch_cache(output_file):
    if batch_cache:
        with file_lock:
            with open(output_file, 'a') as f:
                for item in batch_cache:
                    f.write(json.dumps(item) + "\n")  # 省去 indent 参数
        batch_cache.clear()

def process_single_test_item(bm25, combined_data, test_item, processed_ids):
    if already_processed(test_item, processed_ids):
        return None

    query = test_item['input_code']
    retrieved_docs = bm25_search(bm25, query, combined_data, top_k=TOP_K)
    filtered_results = filter_similar_functions(retrieved_docs, test_item)
    return test_item, filtered_results

# 剩余部分代码保持不变


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

            # 从缓存中获取对应的三类数据
            function_data = function_cache.get(base_name, [])
            class_data = class_cache.get(base_name, [])
            method_data = method_cache.get(base_name, [])

            # 如果三类数据都不存在，跳过该项
            if not (function_data or class_data or method_data):
                continue

            # 构建综合 BM25 索引
            bm25, combined_data = build_bm25_index(
                function_data, class_data, method_data)

            # 提交任务，传递综合数据 combined_data
            futures.append(
                executor.submit(process_single_test_item, bm25,
                                combined_data, item, processed_ids)
            )

        # 等待所有任务完成
        for future in tqdm(as_completed(futures), total=len(futures), desc="处理检索结果"):
            result = future.result()
            if result is not None:
                test_item, retrieved_docs = result
                save_result_to_jsonl(test_item, retrieved_docs, OUTPUT_FILE)
                # 更新已处理条目
                with processed_lock:
                    processed_ids.add(test_item['namespace'])

    # 在主线程中写入剩余数据
    flush_batch_cache(OUTPUT_FILE)

    print(f"BM25 检索结果已保存到 '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
