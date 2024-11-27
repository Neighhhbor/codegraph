import json
import re
import time
from openai import OpenAI, OpenAIError, RateLimitError
import os
import getpass
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置代理（如果需要）
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# Helper function to set environment variables
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# Set environment variables for API keys
_set_env("OPENAI_API_KEY")

# 实例化 OpenAI 客户端
client = OpenAI()

def clean_code_markdown(md_content):
    """
    移除 markdown 格式，提取出 Python 代码
    """
    clean_code = re.sub(r'```Python\n(.*?)\n```', r'\1', md_content, flags=re.DOTALL)
    return clean_code.strip()

# 调用模型生成结果的函数
def call_model(prompt, k=1, retries=3):
    """
    调用 OpenAI 的 chat.completions.create，根据给定的 prompt 生成代码。
    当 k=1 时使用贪心搜索，当 k>1 时使用 nucleus sampling 并生成 k 个样本。
    支持重试机制，在 RateLimitError 时会等待并重试。
    """ 
    for attempt in range(1, retries + 1):
        try:
            if k == 1:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an expert python programmer. Your final output should be the fully completed function code. DO NOT include any additional descriptions in the output."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.0  # 贪心搜索
                )
                # 返回生成的单个文本
                return [clean_code_markdown(response.choices[0].message.content.strip())]
            else:
                # 使用 nucleus sampling 生成 k 个样本
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an expert python programmer. Your final output should be the fully completed function code. DO NOT include any additional descriptions in the output."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.4,  # 设置温度
                    n=k,  # 生成 k 个样本
                    top_p=0.95  # 设置 top-p 参数
                )
                # 返回生成的多个文本列表
                return [clean_code_markdown(choice.message.content.strip()) for choice in response.choices]
        except RateLimitError as e:
            wait_time = 10 * attempt
            print(f"Rate limit reached for prompt. Attempt {attempt}/{retries}. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        except OpenAIError as e:
            print(f"OpenAIError encountered for prompt '{prompt}': {e}")
            return []
        except Exception as e:
            print(f"Error generating completion for prompt '{prompt}': {e}")
            return []
    # 如果超过重试次数仍然失败，返回空列表
    print(f"Failed to generate completion after {retries} attempts for prompt '{prompt}'.")
    return []

# 读取输入的 JSONL 文件
def read_jsonl_file(input_path):
    """
    读取 JSONL 文件，返回每一行的字典形式。
    """
    data = []
    with open(input_path, 'r', encoding='utf-8') as file:
        for line in file:
            data.append(json.loads(line.strip()))
    return data

# 写入单条记录到输出 JSONL 文件
def append_to_jsonl_file(output_path, entry):
    """
    将单条数据附加写入 JSONL 文件。
    """
    with open(output_path, 'a', encoding='utf-8') as file:
        json.dump(entry, file, ensure_ascii=False)
        file.write('\n')

# 处理单条记录
def process_entry(entry, output_path, cache, k=1):
    namespace = entry.get("namespace")
    prompt = entry.get("prompt")
    
    if not namespace or not prompt:
        print(f"Skipping entry due to missing namespace or prompt: {entry}")
        return
    
    # 如果缓存中已经有结果且非空，跳过生成
    if namespace in cache and cache[namespace]:
        print(f"Skipping existing namespace: {namespace}")
        return
    
    print(f"Processing namespace: {namespace}")
    
    # 调用模型生成代码
    completions = call_model(prompt, k=k)
    
    # 更新缓存
    cache[namespace] = completions

    # 将生成结果保存到字典中
    result = {
        "namespace": namespace,
        "completions": completions
    }

    # 立即写入结果到输出 JSONL 文件
    append_to_jsonl_file(output_path, result)

# 处理函数：读取输入文件，调用模型，生成结果，并保存
def process_jsonl_file(input_path, output_path, k=1, limit=None):
    # 读取输入 JSONL 数据
    data = read_jsonl_file(input_path)
    
    # 读取已存在的输出以构建缓存
    cache = {}
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as file:
            for line in file:
                entry = json.loads(line.strip())
                namespace = entry.get("namespace")
                completions = entry.get("completions", [])
                if namespace:
                    cache[namespace] = completions

    # 如果未指定 limit，则处理全部数据
    if limit is None:
        limit = len(data)

    # 并行处理每个条目
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_entry, entry, output_path, cache, k)
            for entry in data[:limit]
        ]
        
        # 确保所有任务完成
        for future in as_completed(futures):
            future.result()  # 捕获任何可能的异常

    print(f"Completed processing. Results saved to {output_path}")

# 主函数
if __name__ == "__main__":
    input_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/Experiments/prompt/without_context/gpt-4-1106_prompt.jsonl"  # 输入文件路径
    output_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Agent/tools/experiments/gpt-4o-mini/without-context/completions.jsonl"  # 输出文件路径
    
    # 设置 k 的值，用于选择生成模式
    k = 1  # 如果希望使用 nucleus sampling 并生成多个结果，可以将 k 设置为 > 1

    # 处理 JSONL 文件，如果不设置 limit，则处理全部数据
    process_jsonl_file(input_path, output_path, k=k, limit=None)
