import os

def combine_files_to_prompt_context(directory, output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # 使用 os.walk 递归遍历目录
        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                # 排除 write_prompt.py 本身
                if filename == "write_prompt.py":
                    continue
                # 只处理 .py 文件
                if filename.endswith('.py'):
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        relative_path = os.path.relpath(file_path, directory)
                        outfile.write(f"--- Start of {relative_path} ---\n")
                        outfile.write(infile.read())
                        outfile.write(f"\n--- End of {relative_path} ---\n\n")

# 调用函数
combine_files_to_prompt_context('./CodeGraph', 'output.txt')
