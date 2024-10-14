import json

def remove_empty_completions(input_path, output_path=None):
    """
    读取 JSONL 文件，过滤掉 completions 为空的条目，并将结果写回文件。
    
    :param input_path: 输入 JSONL 文件路径。
    :param output_path: 输出 JSONL 文件路径。如果为 None，则覆盖输入文件。
    """
    # 如果没有提供 output_path，则覆盖输入文件
    if output_path is None:
        output_path = input_path
    
    # 读取输入文件的内容
    data = []
    with open(input_path, 'r', encoding='utf-8') as file:
        for line in file:
            entry = json.loads(line.strip())
            # 过滤掉 completions 为空的条目
            if entry.get("completions"):
                data.append(entry)
    
    # 将过滤后的结果写入输出文件
    with open(output_path, 'w', encoding='utf-8') as file:
        for entry in data:
            json.dump(entry, file, ensure_ascii=False)
            file.write('\n')
    
    print(f"Filtered data saved to {output_path}. Removed entries with empty completions.")

# 使用示例
if __name__ == "__main__":
    input_path = "gpt-4o-mini_without-tools.jsonl"  # 输入文件路径
    output_path = "gpt-4o-mini_without-tools.jsonl"  # 输出文件路径（可以是同一个路径覆盖原文件）
    
    # 调用函数，删除 completions 为空的条目
    remove_empty_completions(input_path, output_path)
