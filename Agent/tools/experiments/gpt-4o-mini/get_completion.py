import json
from pathlib import Path
from argparse import ArgumentParser

def extract_completions(input_file: Path, output_file: Path):
    """
    从输入 JSONL 文件中提取指定字段，并保存到新的 JSONL 文件中。
    
    :param input_file: 输入 JSONL 文件路径。
    :param output_file: 输出 JSONL 文件路径。
    """
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
            outfile.write(json.dumps(new_data, ensure_ascii=False) + '\n')

    print(f'提取完成，结果保存在 {output_file} 中。')

if __name__ == "__main__":
    # 设置命令行参数解析
    parser = ArgumentParser(description="从 JSONL 文件中提取指定字段并保存到新的 JSONL 文件中。")
    parser.add_argument('--input_file', type=Path, required=True, help='输入 JSONL 文件的路径')
    parser.add_argument('--output_file', type=Path, required=True, help='输出 JSONL 文件的路径')

    # 解析参数
    args = parser.parse_args()

    # 运行提取函数
    extract_completions(args.input_file, args.output_file)
