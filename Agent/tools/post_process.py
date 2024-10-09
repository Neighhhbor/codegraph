import json
import re
from pathlib import Path
from argparse import ArgumentParser

def extract_code(completion_text):
    """
    从给定的生成文本中提取代码部分。
    """
    # 使用正则表达式匹配代码块
    code_pattern = re.compile(r'```(?:python)?\n(.*?)```', re.DOTALL)
    code_matches = code_pattern.findall(completion_text)

    if code_matches:
        # 返回第一个匹配到的代码块
        return code_matches[0].strip()
    else:
        # 如果没有代码块，则直接提取 'def' 开头到文档末尾的部分作为代码
        code_start = completion_text.find("def ")
        if code_start != -1:
            return completion_text[code_start:].strip()
        return ""


def process_jsonl_file(input_file: Path, output_file: Path):
    """
    从JSONL文件中读取生成的文本并提取代码部分保存到输出文件中。
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for line in f:
                entry = json.loads(line)
                namespace = entry.get('namespace', 'unknown')
                completion = entry.get('completions', '')
                
                # 提取纯代码
                code = extract_code(completion)

                # 创建新的 JSON 对象，包含提取后的代码
                new_entry = {
                    "namespace": namespace,
                    "completions": code
                }
                
                # 将新对象写入输出文件
                out_f.write(json.dumps(new_entry) + '\n')

    print(f"提取完成，处理后的数据已保存到 {output_file}")

if __name__ == "__main__":
    parser = ArgumentParser(description="从生成的模型输出中提取代码部分")
    parser.add_argument('--input_file', type=Path, required=True, help='输入JSONL文件路径')
    parser.add_argument('--output_file', type=Path, required=True, help='输出JSONL文件路径，用于保存提取的纯代码')

    args = parser.parse_args()
    process_jsonl_file(args.input_file, args.output_file)
