import json

# 输入文件名
file_name = 'completions.jsonl'

# 临时存储清理后的内容
cleaned_data = []

# 读取 JSONL 文件并删除 completions 是空字符串的行
with open(file_name, 'r', encoding='utf-8') as infile:
    for line in infile:
        try:
            # 加载每一行的 JSON 数据
            data = json.loads(line.strip())
            # 如果 completions 不为空字符串，则保留这行数据
            if data.get("completions", None) != "":
                cleaned_data.append(data)
        except json.JSONDecodeError:
            # 如果某一行不是有效 JSON，则跳过或记录日志（可选）
            continue

# 将清理后的内容写回原文件，覆盖原文件
with open(file_name, 'w', encoding='utf-8') as outfile:
    for item in cleaned_data:
        outfile.write(json.dumps(item) + '\n')

print(f"清理完成，原文件已被覆盖：{file_name}")
