import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAIError
import random
# Import the agent-related functions
from agent import run_agent_for_entry

API_KEYS = [
   "sk-1x89JfMTNXdPX1mF58B04e0c06Df4d2a90F7EcAb844a64C0",
   "sk-XRiNC1NpxEH3RMfUD955541734484598B39b8173423aEeCd",
   "sk-JFdL055uB2VYCYa5D0188d959b294bC9BdE75c44F930CcC9",
   "sk-I84YMroikrr9B1jDA8Fd55Aa7c7142098b115a2072D0A271"
]
os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"

# 配置文件路径常量
PROMPT_FILE = "./prompts.jsonl"  # 替换为你的 prompt.jsonl 文件路径
OUTPUT_FILE = "./rgrgrg_result/completions.jsonl"                                               # 输出的 jsonl 文件路径

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

def process_single_entry(entry, existing_namespaces, api_key, retries=3):
    """
    处理单个 entry，执行 agent 流程并返回结果。
    """
    os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"
    namespace = entry.get("namespace")
    prompt = entry.get("prompt")

    if not namespace or not prompt:
        return None, f"Skipping entry: Missing namespace or prompt."
    if namespace in existing_namespaces:
        return None, f"Skipping entry: Namespace {namespace} already has a completion."

    print(f"Running agent for namespace: {namespace} with API key...")

    for attempt in range(1, retries + 1):
        try:
            # 传入特定的 API key
            completion = run_agent_for_entry(prompt, api_key)
            clean_completion = clean_code_markdown(completion)
            result = {
                "namespace": namespace,
                "completions": clean_completion
            }
            return result, None
        except OpenAIError as e:
            wait_time = 10 ** attempt
            print(e)
            print(f"Rate limit reached for {namespace}. Attempt {attempt}/{retries}. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        except Exception as e:
            return None, f"Error in processing {namespace}: {e}"

    return None, f"Failed to process {namespace} after {retries} retries due to rate limit."


def generate_agent_outputs_concurrently(data, existing_namespaces, max_workers=8):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, entry in enumerate(data):
            api_key = API_KEYS[random.randint(0, len(API_KEYS) - 1)]  # 随机分配 API key
            futures[executor.submit(process_single_entry, entry, existing_namespaces, api_key)] = entry

        for future in as_completed(futures):
            try:
                result, error = future.result()
                if error:
                    print(error)
                    continue
                if result:
                    write_output_to_jsonl([result], OUTPUT_FILE)
                    results.append(result)
            except Exception as e:
                print(f"Error processing entry: {e}")

        print("Executor shutdown complete.")
    return results


if __name__ == "__main__":

    # 读取 prompt.jsonl 的所有数据用于测试
    prompt_data = read_prompts_from_jsonl(PROMPT_FILE)

    # 加载已有的补全结果
    existing_namespaces = load_existing_completions(OUTPUT_FILE)

    # 使用并发执行 agent 并生成补全代码
    agent_results = generate_agent_outputs_concurrently(prompt_data, existing_namespaces)

    print(f"Generated {len(agent_results)} new entries and saved to {OUTPUT_FILE}")

    # 强制退出，确保所有资源释放
    sys.exit(0)
