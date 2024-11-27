import json

# 示例文件路径
embedding_file = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/embedding/embedding_retrieved.jsonl"
bm25_file = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/BM25/bm25_retrieved.jsonl"

def filter_groundtruth_matches(data):
    """
    过滤掉与 `signature` 相同的检索结果。
    """
    for item in data:
        target_signature = item['signature']
        # 过滤掉签名相同的条目
        item['retrieved'] = [
            result for result in item['retrieved']
            if result['similar_signature'].split('.')[-1] != target_signature
        ]
    return data

# 加载嵌入检索结果
with open(embedding_file, 'r') as f:
    embedding_data = [json.loads(line) for line in f ]

# 过滤嵌入检索结果中的ground truth
embedding_data = filter_groundtruth_matches(embedding_data)

# 保存过滤后的嵌入检索结果
with open("filtered_embedding_results.json", "w") as f:
    json.dump(embedding_data, f, ensure_ascii=False, indent=4)

# 加载BM25检索结果
with open(bm25_file, 'r') as f:
    bm25_data = [json.loads(line) for line in f ]

# 过滤BM25检索结果中的ground truth
bm25_data = filter_groundtruth_matches(bm25_data)

# 保存过滤后的BM25检索结果
with open("filtered_bm25_results.json", "w") as f:
    json.dump(bm25_data, f, ensure_ascii=False, indent=4)

print("过滤完成，已保存至 'filtered_embedding_results.json' 和 'filtered_bm25_results.json'")
