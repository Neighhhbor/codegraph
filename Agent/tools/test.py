import json

def read_jsonl(file_path):
    """
    读取 JSONL 文件并将其解析为 Python 对象列表。
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                data.append(json.loads(line.strip()))
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e} in line: {line.strip()}")
    return data

def transform_completion_path(completion_path):
    """
    转换 `completion_path` 为符合 Python 导入规则的路径。
    去掉类别部分，并将 `/` 替换为 `.`。
    """
    path_without_category = "/".join(completion_path.split('/')[1:])  # 去掉第一部分
    path_without_extension = path_without_category.replace('.py', '')
    transformed_path = path_without_extension.replace('/', '.')
    return transformed_path

def generate_target_function_node(namespace, transformed_path):
    """
    基于两重循环逐步匹配生成 target_function_node，避免重复部分。
    """
    # 将 `transformed_path` 和 `namespace` 分割为各自的部分
    transformed_parts = transformed_path.split('.')
    namespace_parts = namespace.split('.')

    # 记录重叠的最大长度
    max_overlap_length = 0

    # 使用两重循环找到最长的重叠部分
    for i in range(len(transformed_parts)):
        for j in range(len(namespace_parts)):
            # 找到相同的部分，并逐步向后检查
            overlap_length = 0
            while (i + overlap_length < len(transformed_parts) and 
                   j + overlap_length < len(namespace_parts) and 
                   transformed_parts[i + overlap_length] == namespace_parts[j + overlap_length]):
                overlap_length += 1

            # 更新最大重叠长度
            if overlap_length > max_overlap_length:
                max_overlap_length = overlap_length

    # 构建最终路径：
    # 1. 保留 `transformed_path` 的所有部分
    result_parts = transformed_parts

    # 2. 添加 `namespace` 中未匹配的部分（从重叠的后一个位置开始）
    result_parts.extend(namespace_parts[max_overlap_length:])

    # 将结果拼接成最终路径
    final_path = '.'.join(result_parts)
    return final_path

def test_generate_target_function_node():
    """
    测试 `generate_target_function_node` 的各种情况。
    """
    test_cases = [
        {
            "namespace": "playhouse.kv.KeyValue.get",
            "completion_path": "Software-Development/peewee/playhouse/kv.py",
            "expected": "peewee.playhouse.kv.KeyValue.get"
        },
        {
            "namespace": "kv.KeyValue.get",
            "completion_path": "Software-Development/peewee/playhouse/kv.py",
            "expected": "peewee.playhouse.kv.KeyValue.get"
        },
        {
            "namespace": "playhouse.kv.KeyValue",
            "completion_path": "Software-Development/peewee/playhouse/kv.py",
            "expected": "peewee.playhouse.kv.KeyValue"
        },
        {
            "namespace": "KeyValue.get",
            "completion_path": "Software-Development/peewee/playhouse/kv.py",
            "expected": "peewee.playhouse.kv.KeyValue.get"
        },
        {
            "namespace": "kv.get",
            "completion_path": "Software-Development/peewee/playhouse/kv.py",
            "expected": "peewee.playhouse.kv.get"
        }
    ]

    for idx, case in enumerate(test_cases):
        namespace = case["namespace"]
        completion_path = case["completion_path"]
        expected = case["expected"]

        transformed_path = transform_completion_path(completion_path)
        result = generate_target_function_node(namespace, transformed_path)
        
        if result == expected:
            print(f"Test case {idx + 1} passed.")
        else:
            print(f"Test case {idx + 1} failed: expected '{expected}', but got '{result}'")

# 调用测试函数
test_generate_target_function_node()
