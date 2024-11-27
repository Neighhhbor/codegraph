import json
import logging
import os
import getpass
import time
import threading
from openai import OpenAI, OpenAIError, RateLimitError
from concurrent.futures import ThreadPoolExecutor, as_completed
from key import KEYS
# 设置代理（如果需要）
# os.environ['http_proxy'] = "http://127.0.0.1:7890"
# os.environ['https_proxy'] = "http://127.0.0.1:7890"
# os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 设置 API KEY 和自定义 API BASE URL
os.environ["OPENAI_API_KEY"] = KEYS[0]
os.environ["OPENAI_BASE_URL"] = "http://15.204.101.64:4000/v1"
# Helper function to set environment variables
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# Set environment variables for API keys
_set_env("OPENAI_API_KEY")

# Instantiate OpenAI client with the custom base URL
client = OpenAI()

# Initialize a lock for thread-safe file writing
file_lock = threading.Lock()

def call_model(prompt, retries=5):
    """
    Call OpenAI's GPT-4o model to generate code based on the given prompt.
    Implements exponential backoff in case of RateLimitError.
    """
    wait_time = 1  # Initial wait time for exponential backoff
    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert python programmer. Your final output should be the fully completed function code. DO NOT include any additional descriptions in the output."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except RateLimitError as e:
            logging.warning(f"Rate limit reached for prompt. Attempt {attempt}/{retries}. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            wait_time *= 2  # Double the wait time for each retry (exponential backoff)
        except OpenAIError as e:
            logging.error(f"OpenAIError encountered for prompt '{prompt[:100]}': {e}")
            return ""
        except Exception as e:
            logging.error(f"Error generating completion for prompt '{prompt[:100]}': {e}")
            return ""

    logging.error(f"Failed to generate completion after {retries} attempts for prompt '{prompt[:100]}'.")
    return ""

# Write to output JSONL file
def append_to_jsonl_file(output_path, entry):
    """
    Append a single record to the output JSONL file.
    """
    with file_lock:  # Ensure only one thread writes to the file at a time
        with open(output_path, 'a', encoding='utf-8') as file:
            json.dump(entry, file, ensure_ascii=False)
            file.write('\n')

def process_entry(entry, output_path, cache):
    namespace = entry.get("namespace")
    prompt = entry.get("prompt")

    if not namespace or not prompt:
        logging.warning(f"跳过缺少 namespace 或 prompt 的条目: {entry}")
        return

    if namespace in cache and cache[namespace]:
        logging.info(f"跳过已存在的 namespace: {namespace}")
        return

    logging.info(f"处理 namespace: {namespace}")

    completion = call_model(prompt)

    if not completion:
        logging.warning(f"未生成 namespace 的完成结果: {namespace}。跳过写入输出。")
        return

    if "completions" not in cache:
        cache[namespace] = []
    cache[namespace].append(completion)

    result = {
        "namespace": namespace,
        "completions": cache[namespace]
    }

    append_to_jsonl_file(output_path, result)

def process_jsonl_file(input_path, output_path, exper1_path, limit=None):
    # 读取 exper1_completion.jsonl 文件中的 namespace
    exper1_namespaces = set()
    with open(exper1_path, 'r', encoding='utf-8') as file:
        for line in file:
            entry = json.loads(line.strip())
            namespace = entry.get("namespace")
            if namespace:
                exper1_namespaces.add(namespace)

    # 读取输入 JSONL 数据
    data = []
    with open(input_path, 'r', encoding='utf-8') as file:
        for line in file:
            entry = json.loads(line.strip())
            if entry.get("namespace") in exper1_namespaces:
                data.append(entry)

    # 读取现有输出以构建缓存
    cache = {}
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as file:
            for line in file:
                entry = json.loads(line.strip())
                namespace = entry.get("namespace")
                completions = entry.get("completions", [])
                if namespace:
                    cache[namespace] = completions

    # 如果未指定限制,则处理所有条目
    if limit is None:
        limit = len(data)

    # 使用 ThreadPoolExecutor 并行处理每个条目
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_entry, entry, output_path, cache)
            for entry in data[:limit]
        ]

        # 确保所有任务完成
        for future in as_completed(futures):
            try:
                future.result()  # 在此处引发任何异常
            except Exception as e:
                logging.error(f"并行处理期间出现异常: {e}")

    logging.info(f"处理完成。结果已保存到 {output_path}")

if __name__ == "__main__":
    # 文件路径
    input_path = "/home/shixianjie/codegraph/codegraph/DevEval/Experiments/prompt/local_infilling/gpt-4-1106_prompt.jsonl"
    output_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/gpt-4o/ablation_completion.jsonl"
    exper1_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/gpt-4o/exper1_completion.jsonl"

    # 处理 JSONL 文件,不指定限制以处理所有条目
    process_jsonl_file(input_path, output_path, exper1_path, limit=None)
