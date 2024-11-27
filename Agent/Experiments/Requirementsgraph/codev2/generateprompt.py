import json
import os
from tqdm import tqdm

def read_jsonl(file_path):
    """
    读取 JSONL 文件并将其解析为 Python 对象列表。
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                data.append(json.loads(line.strip()))
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e} in line: {line.strip()}")
    return data

def save_prompts_to_jsonl(prompts, output_file):
    """
    将生成的 prompt 列表保存为 JSONL 文件。
    """
    with open(output_file, 'w', encoding='utf-8') as file:
        for prompt in prompts:
            json.dump(prompt, file)
            file.write('\n')

def build_code_map(repo_path, reponame):
    """
    针对当前处理的数据，动态生成一个临时的 namespace -> code 的映射。

    参数:
    - repo_path (str): 仓库路径
    - reponame (str): 当前项目的名称

    返回:
    - code_map (dict): 当前项目的 namespace -> code 映射
    """
    code_map = {}
    files = [
        os.path.join(repo_path, f"{reponame}_functions.json"),
        os.path.join(repo_path, f"{reponame}_methods.json"),
        os.path.join(repo_path, f"{reponame}_classes.json")
    ]
    # 遍历文件，动态生成 code_map
    for file in files:
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        item = json.loads(line.strip())
                        namespace = item.get("name", "")
                        code = item.get("code", "")
                        
                        # 添加到 code_map
                        if namespace and namespace not in code_map:
                            code_map[namespace] = {
                                "code": code,
                                "path": item.get("path", "")
                            }
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON in file {file}: {e}")
    
    return code_map

def extract_related_code(dependencies, code_map):
    """
    从依赖中提取相关代码。

    参数:
    - dependencies (dict): 包含 child_requirement, context_requirement, similarity_requirement 的依赖关系
    - code_map (dict): 当前项目的 namespace -> code 映射

    返回:
    - related_code (dict): 包含各类依赖相关代码的字典
    """
    related_code = {key: [] for key in dependencies}
    
    for category, namespaces in dependencies.items():
        for ns in namespaces:
            if ns in code_map:
                related_code[category].append({
                    "namespace": ns,
                    "code": code_map[ns]["code"],
                    "path": code_map[ns]["path"]
                })
    
    return related_code

def generate_prompt(data, related_code):
    """
    基于当前数据和相关代码生成 prompt。

    参数:
    - data (dict): 当前的元数据
    - related_code (dict): 提取的相关代码

    返回:
    - prompt (str): 生成的 prompt 字符串
    """
    namespace = data.get("namespace", "")
    input_code = data.get("input_code", "")

    # 构建目标代码部分
    prompt = f"Code to complete:\n```python\n{input_code}\n```\n\n"
    prompt += "Refer to the related code below:\n\n"

    # 构建相关代码部分
    for category, codes in related_code.items():
        if codes:
            prompt += f"{category.capitalize()}:\n"
            for code_item in codes:
                prompt += (
                    f"Namespace: {code_item['namespace']}\n"
                    f"Code:\n"
                    f"```python\n{code_item['code']}\n```\n"
                )

    return prompt.strip()




def process_data_and_generate_prompts(filtered_file, meta_file, repo_path, output_file):
    """
    读取依赖信息和元信息，动态生成 prompt，并保存到输出文件。

    参数:
    - filtered_file (str): 包含依赖信息的 JSONL 文件路径
    - meta_file (str): 包含元信息的 JSONL 文件路径
    - repo_path (str): 仓库路径
    - output_file (str): 输出的 JSONL 文件路径
    """
    # 读取依赖信息和元信息
    dependencies_data = read_jsonl(filtered_file)
    meta_data = {item["namespace"]: item for item in read_jsonl(meta_file)}

    prompts = []

    for dep in tqdm(dependencies_data, desc="Processing Data", unit="entry"):
        namespace = dep.get("namespace", "")
        dependencies = dep.get("dependency", {})
        
        # 找到对应的元信息
        if namespace not in meta_data:
            print(f"Warning: Namespace `{namespace}` not found in metadata.")
            continue
        
        data = meta_data[namespace]
        project_path = data.get("project_path", "")
        if not project_path:
            print(f"Warning: Project path not found for namespace `{namespace}`.")
            continue

        # 动态生成当前项目的 code_map
        reponame = project_path.split("/")[-1]
        # print(reponame)
        code_map = build_code_map(repo_path, reponame)
        # print(code_map)
        # 提取相关代码
        related_code = extract_related_code(dependencies, code_map)
        # print(related_code)
        # 生成 prompt
        prompt_text = generate_prompt(data, related_code)

        # 保存 prompt
        prompts.append({
            "namespace": namespace,
            "input_code": data.get("input_code", ""),
            "prompt": prompt_text,
        })

    # 保存生成的 prompts 到 JSONL 文件
    save_prompts_to_jsonl(prompts, output_file)

# 调用主流程
if __name__ == "__main__":
    filtered_file = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/Requirementsgraph/codev2/filtered.jsonl"
    meta_file = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/promptelements/LM_prompt_elements_merged.jsonl"
    repo_path = "/home/shixianjie/codegraph/codegraph/Agent/repocode"
    output_file = "./prompt_require.jsonl"

    process_data_and_generate_prompts(filtered_file, meta_file, repo_path, output_file)
