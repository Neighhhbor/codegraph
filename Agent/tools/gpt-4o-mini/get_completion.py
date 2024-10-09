import json

# 输入和输出文件名
input_file = '/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Agent/tools/gpt-4o-mini/completion.jsonl'
output_file = '/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Agent/tools/gpt-4o-mini/gpt-4o-mini-completion.jsonl'

# 打开输入文件，逐行读取
with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
    for line in infile:
        # 解析每一行的 JSON 数据
        data = json.loads(line.strip())
        
        # 提取需要的字段
        new_data = {
            "namespace": data.get("namespace"),
            "completion": data.get("completion"),
            "idx": data.get("idx")
        }
        
        # 将新的 JSON 数据写入输出文件
        outfile.write(json.dumps(new_data) + '\n')

print(f'提取完成，结果保存在 {output_file} 中。')
