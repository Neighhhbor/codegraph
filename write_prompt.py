import os

def combine_files_to_prompt_context(directory, output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if filename == "write_prompt.py":
                continue
            if os.path.isfile(file_path) and file_path.endswith('.py'):
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(f"--- Start of {filename} ---\n")
                    outfile.write(infile.read())
                    outfile.write(f"\n--- End of {filename} ---\n\n")

# 调用函数
combine_files_to_prompt_context('./', 'output.txt')
