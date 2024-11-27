import json

# 输入和输出文件路径
embedding_data_file = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/RepoCoder/retrival/rgrg/top5_retrieved_filtered_rgrg.jsonl"  # embedding 的过滤数据文件
output_embedding_prompts_file = "prompts.jsonl"  # 输出 embedding 的 JSONL 文件路径

# 生成 prompt 的函数
def generate_prompt(input_code, similar_code_snippets, method="embedding"):
    """
    为单个 case 生成 prompt，包含指定方法（仅 embedding）。
    """
    prompt = f"The code to be completed is:\n```Python\n{input_code}\n```\n\n"
    if similar_code_snippets:
        prompt += "Here are some similar code snippets to help with the completion:\n"
        for idx, item in enumerate(similar_code_snippets, start=1):
            code_snippet = item.get('similar_code', '')
            similarity_score = item.get('similarity_score', 0)  # 仅使用 similarity_score
            prompt += f"\n[{idx}] Similar code snippet (Score: {similarity_score:.2f}):\n```Python\n{code_snippet}\n```\n"

    prompt += "\nCompleted code:"
    return prompt

# 读取并生成 prompts
def generate_prompts_for_embedding(embedding_file, output_embedding_file):
    # 处理 embedding 数据并生成 prompts
    with open(embedding_file, 'r') as f:
        embedding_cases = [json.loads(line) for line in f]

    with open(output_embedding_file, 'w') as f:
        for case in embedding_cases:
            input_code = case.get('inputcode', '')
            similar_code_snippets = case.get('retrieved', [])

            # 生成 prompt
            prompt_text = generate_prompt(input_code, similar_code_snippets, method="embedding")

            # 保存 embedding prompt
            prompt_entry = {
                "namespace": case.get('namespace'),
                "project_path": case.get('project_path'),
                "signature": case.get('signature'),
                "method": "embedding",
                "prompt": prompt_text
            }
            f.write(json.dumps(prompt_entry) + "\n")

    print(f"Prompts for embedding have been saved to {output_embedding_file}")

# 生成 embedding 的 prompts 文件
generate_prompts_for_embedding(embedding_data_file, output_embedding_prompts_file)
