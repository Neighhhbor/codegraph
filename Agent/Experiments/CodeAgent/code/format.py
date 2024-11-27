import json

# 输入和输出文件路径
input_file = 'path/to/your/original_file.jsonl'
output_file = 'path/to/your/formatted_file.jsonl'

def format_jsonl_file(input_file, output_file, indent=4):
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            # 解析 JSON 对象
            json_obj = json.loads(line)
            # 格式化 JSON 对象并写入新文件
            formatted_json = json.dumps(json_obj, indent=indent)
            outfile.write(formatted_json + '\n')

# 调用函数来格式化文件
format_jsonl_file(input_file, output_file)
