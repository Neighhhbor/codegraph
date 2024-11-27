import json
import re

# 输入和输出文件路径
file_path = "completions.jsonl"
output_file = "completions.jsonl"

# 读取 JSONL 文件
with open(file_path, 'r', encoding='utf-8') as f:
    data = [json.loads(line.strip()) for line in f.readlines()]

# 清理代码块并更新数据
for entry in data:
    completion = entry.get("completions")
    # 使用正则表达式清理所有 Markdown 格式的代码块（忽略大小写）
    clean_code = re.sub(r'```(?:python)?\n(.*?)\n```', r'\1', completion, flags=re.IGNORECASE | re.DOTALL).strip()
    entry["completions"] = clean_code  # 更新为清理后的字符串

# 写入清理后的数据到新的 JSONL 文件
with open(output_file, 'w', encoding='utf-8') as f:
    for entry in data:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

print(f"清理后的数据已保存到 {output_file}")
