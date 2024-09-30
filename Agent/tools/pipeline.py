import json
import os
import re

# Import the agent-related functions
from test_agent import run_agent_for_entry

# 配置文件路径常量
PROMPT_FILE = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Agent/prompt.jsonl"  # 替换为你的 prompt.jsonl 文件路径
DATA_FILE = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/data.jsonl"      # 替换为你的 data.jsonl 文件路径
OUTPUT_FILE = "gpt-4o-mini.jsonl"                                                # 输出的 jsonl 文件路径

def read_prompts_from_jsonl(file_path, max_entries=None):
    """
    读取 JSONL 文件中的数据，并返回包含 `namespace` 和 `prompt` 字段的列表。
    可以选择指定要读取的最大条目数量。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = [json.loads(line.strip()) for line in lines]

    if max_entries:
        data = data[:max_entries]

    return data

def read_data_jsonl(file_path):
    """
    读取 data.jsonl 文件，返回每个 `namespace` 对应的 `graph_name`。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = {}
    for line in lines:
        entry = json.loads(line.strip())
        namespace = entry.get("namespace")
        project_path = entry.get("project_path", "")
        graph_name = os.path.basename(project_path)  # 从 project_path 中提取图的名称
        graph_name = graph_name.split(".")[0]  # 去除扩展名部分
        data[namespace] = graph_name

    return data

def write_output_to_jsonl(output_data, file_path):
    """
    将生成的输出数据写入到 JSONL 文件中。
    """
    with open(file_path, 'a', encoding='utf-8') as f:  # 使用 'a' 模式追加写入每条输出
        for entry in output_data:
            f.write(json.dumps(entry) + '\n')

def clean_code_markdown(md_content):
    """
    移除 markdown 格式，提取出 Python 代码
    """
    # 使用正则表达式去除 ```python 和 ``` 等标记
    clean_code = re.sub(r'```python\n(.*?)\n```', r'\1', md_content, flags=re.DOTALL)
    return clean_code.strip()

def generate_agent_outputs(data, graph_data, max_count=5):
    """
    对每条 `namespace` 和 `prompt` 执行 agent 流程，并将结果保存为 JSONL 格式。
    """
    results = []
    count = 0

    for entry in data:
        namespace = entry.get("namespace")
        target_node_label = entry.get("target_function_node_label")
        prompt = entry.get("prompt")

        if not namespace or not prompt:
            print(f"Skipping entry {count}: Missing namespace or prompt.")
            continue

        # 从 data.jsonl 获取图的名称
        graph_name = graph_data.get(namespace)
        if not graph_name:
            print(f"Skipping entry {count}: Missing graph name for namespace {namespace}.")
            continue

        # 调用 agent 生成补全代码
        print(f"Running agent for namespace: {namespace} target{target_node_label} (Entry {count + 1})...")
        completion = run_agent_for_entry(target_node_label, prompt, graph_name)

        # 移除 markdown 格式，保留纯代码
        clean_completion = clean_code_markdown(completion)

        # 生成 JSONL 格式的输出
        result = {
            "namespace": namespace,
            "completion": clean_completion  # 使用清理后的代码
        }

        results.append(result)
        count += 1

        # 每生成一个条目后立即写入到文件中，防止中途程序出错导致数据丢失
        write_output_to_jsonl([result], OUTPUT_FILE)

        # 控制生成数量
        if count >= max_count:
            break

    return results

if __name__ == "__main__":
    # 读取 data.jsonl 中的图信息
    graph_data = read_data_jsonl(DATA_FILE)

    # 读取 prompt.jsonl 的前 5 条数据用于测试
    prompt_data = read_prompts_from_jsonl(PROMPT_FILE, max_entries=3)

    # 执行 agent 并生成补全代码
    agent_results = generate_agent_outputs(prompt_data, graph_data, max_count=3)

    print(f"Generated {len(agent_results)} entries and saved to {OUTPUT_FILE}")


