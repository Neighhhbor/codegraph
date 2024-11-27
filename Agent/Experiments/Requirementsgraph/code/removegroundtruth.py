import json

SIMILARITY_THRESHOLD = 80  # 设定相似度阈值

def is_parent_or_child(parent, child):
    """检查 parent 和 child 是否是父子路径关系"""
    # 判断 child 是否是 parent 的扩展（即 child 比 parent 多了一些路径部分）
    # 例如：parent="mrjob.parse.is_s3_uri", child="mrjob.mrjob.parse.parse_s3_uri"
    # 这时 child 是 parent 的扩展，我们认为它们一致
    if parent in child:
        # 检查 child 是否包含 parent，并且 parent 和 child 之间的差异至少有一部分
        return True
    return False

def filter_by_parent_or_child(data):
    """根据父子路径关系来过滤数据"""
    filtered_data = []
    
    for item in data:
        namespace = item.get("namespace")
        child_requirements = item.get("dependency", {}).get("child_requirement", [])
        context_requirements = item.get("dependency", {}).get("context_requirement", [])
        similarity_requirements = item.get("dependency", {}).get("similarity_requirement", [])
        
        # 筛选 child_requirements
        child_requirements_filtered = [
            child for child in child_requirements
            if not is_parent_or_child(namespace, child)  # 筛掉父子路径关系的项
        ]
        
        # 筛选 context_requirements
        context_requirements_filtered = [
            context for context in context_requirements
            if not is_parent_or_child(namespace, context)  # 筛掉父子路径关系的项
        ]
        
        # 筛选 similarity_requirements
        similarity_requirements_filtered = [
            similarity for similarity in similarity_requirements
            if not is_parent_or_child(namespace, similarity)  # 筛掉父子路径关系的项
        ]
        
        # 更新依赖项
        item["dependency"]["child_requirement"] = child_requirements_filtered
        item["dependency"]["context_requirement"] = context_requirements_filtered
        item["dependency"]["similarity_requirement"] = similarity_requirements_filtered
        
        # 保留该项数据
        filtered_data.append(item)
    
    return filtered_data

# 示例数据加载
data = []
with open('final_data_v2.jsonl', 'r', encoding='utf-8') as f:
    # 读取 JSONL 文件，每行是一个 JSON 对象
    data = [json.loads(line) for line in f]

# 使用过滤算法（基于父子路径关系匹配）
filtered_by_parent_or_child = filter_by_parent_or_child(data)

# 将筛选结果保存到文件
with open('filtered.jsonl', 'w', encoding='utf-8') as f:
    # 写入每个过滤后的项，每个项在单独的一行
    for item in filtered_by_parent_or_child:
        json.dump(item, f, ensure_ascii=False)
        f.write('\n')

print("筛选结果已保存到文件：filtered.jsonl")
