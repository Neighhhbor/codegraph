import json
from collections import defaultdict
import re
# 文件路径
file1_path = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/promptelements/LM_prompt_elements_merged.jsonl"  # 替换为你的文件 1 路径
file2_path = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/RepoCoder/generation/rgrg_result/completions.jsonl"  # 替换为你的文件 2 路径
output_path = "metadata_rgrg.jsonl"  # 输出文件路径

def load_jsonl(file_path):
    """加载 JSONL 文件为列表"""
    with open(file_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def save_jsonl(data, file_path):
    """保存列表为 JSONL 文件"""
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")


def clean_completions(completions):
    """
    使用正则表达式清理 completions 字段，去掉以 ```Python 或 ``` 包裹的内容
    :param completions: 原始 completions 列表
    :return: 清理后的 completions 列表
    """
    cleaned_completions = []
    for completion in completions:
        # 正则去除 ```Python 或 ``` 开头及 ``` 结尾
        cleaned_code = re.sub(r"^```(?:Python|python)?\n|\n```$", "", completion.strip(), flags=re.IGNORECASE)
        cleaned_completions.append(cleaned_code)
    return cleaned_completions

def merge_files(file1_data, file2_data, filters=None):
    """
    按 namespace 字段整合两个文件的内容，并支持筛选部分信息
    :param file1_data: 文件 1 数据
    :param file2_data: 文件 2 数据
    :param filters: 筛选的字段集合（列表）
    :return: 合并后的数据
    """
    # 将文件 2 的内容按 namespace 索引
    file2_dict = {entry["namespace"]: entry for entry in file2_data}

    merged_data = []
    for item in file1_data:
        namespace = item["namespace"]
        merged_item = item.copy()  # 保留文件 1 的内容

        if namespace in file2_dict:
            # 整合文件 2 的内容
            merged_item["completions"] = [file2_dict[namespace].get("completions", "")]
            merged_item["completions"] = clean_completions(merged_item["completions"])
        # 如果定义了筛选字段，则只保留这些字段
        if filters:
            merged_item = {key: merged_item[key] for key in filters if key in merged_item}

        merged_data.append(merged_item)

    return merged_data

def main():
    # 加载文件内容
    file1_data = load_jsonl(file1_path)
    file2_data = load_jsonl(file2_path)

    # 定义需要保留的字段（筛选部分信息）
    filters = ["namespace", "project_path", "input_code", "completions"]

    # 合并内容并筛选部分信息
    merged_data = merge_files(file1_data, file2_data, filters=filters)

    # 保存合并和筛选结果
    save_jsonl(merged_data, output_path)
    print(f"Filtered and merged data saved to {output_path}")

if __name__ == "__main__":
    main()