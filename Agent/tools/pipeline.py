import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAIError

# Import the agent-related functions
from test_agent import run_agent_for_entry

# 配置文件路径常量
PROMPT_FILE = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Agent/prompt.jsonl"  # 替换为你的 prompt.jsonl 文件路径
DATA_FILE = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/data.jsonl"    # 替换为你的 data.jsonl 文件路径
OUTPUT_FILE = "gpt-4o-mini.jsonl"                                               # 输出的 jsonl 文件路径

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

def load_existing_completions(file_path):
    """
    读取已有的补全结果，返回一个包含所有 `namespace` 的集合。
    """
    if not os.path.exists(file_path):
        return set()

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    existing_namespaces = {json.loads(line.strip()).get("namespace") for line in lines if line.strip()}
    return existing_namespaces

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
    clean_code = re.sub(r'```python\n(.*?)\n```', r'\1', md_content, flags=re.DOTALL)
    return clean_code.strip()

def process_single_entry(entry, graph_data, existing_namespaces, retries=3):
    """
    处理单个 entry，执行 agent 流程并返回结果。
    """
    namespace = entry.get("namespace")
    target_node_label = entry.get("target_function_node_label")
    prompt = entry.get("prompt")

    if not namespace or not prompt:
        return None, f"Skipping entry: Missing namespace or prompt."

    if namespace in existing_namespaces:
        return None, f"Skipping entry: Namespace {namespace} already has a completion."

    graph_name = graph_data.get(namespace)
    if not graph_name:
        return None, f"Skipping entry: Missing graph name for namespace {namespace}."

    print(f"Running agent for namespace: {namespace} target {target_node_label}...")

    for attempt in range(1, retries + 1):
        try:
            completion = run_agent_for_entry(target_node_label, prompt, graph_name)
            clean_completion = clean_code_markdown(completion)
            result = {
                "namespace": namespace,
                "completions": clean_completion
            }
            return result, None
        except OpenAIError as e:
            wait_time = 10 * attempt
            print(f"Rate limit reached for {namespace}. Attempt {attempt}/{retries}. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        except Exception as e:
            return None, f"Error in processing {namespace}: {e}"

    return None, f"Failed to process {namespace} after {retries} retries due to rate limit."

def generate_agent_outputs_concurrently(data, graph_data, existing_namespaces, max_workers=2):
    """
    使用并发处理每条 `namespace` 和 `prompt`，并将结果保存为 JSONL 格式。
    """
    results = []

    # 使用线程池执行并发任务
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_entry, entry, graph_data, existing_namespaces): entry for entry in data
        }

        for future in as_completed(futures):
            try:
                result, error = future.result()
                if error:
                    print(error)
                    continue

                if result:
                    # 每生成一个条目后立即写入到文件中，防止中途程序出错导致数据丢失
                    write_output_to_jsonl([result], OUTPUT_FILE)
                    results.append(result)
            except Exception as e:
                print(f"Error processing entry: {e}")

        print("Executor shutdown complete.")

    return results

if __name__ == "__main__":
    # 读取 data.jsonl 中的图信息
    graph_data = read_data_jsonl(DATA_FILE)

    # 读取 prompt.jsonl 的所有数据用于测试
    prompt_data = read_prompts_from_jsonl(PROMPT_FILE)

    # 加载已有的补全结果
    existing_namespaces = load_existing_completions(OUTPUT_FILE)

    # 使用并发执行 agent 并生成补全代码
    agent_results = generate_agent_outputs_concurrently(prompt_data, graph_data, existing_namespaces)

    print(f"Generated {len(agent_results)} new entries and saved to {OUTPUT_FILE}")

    # 强制退出，确保所有资源释放
    sys.exit(0)
