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
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 设置 API KEY 和自定义 API BASE URL
os.environ["OPENAI_API_KEY"] = KEYS[0]
os.environ["OPENAI_BASE_URL"] = 'https://api.openai-proxy.com/v1'
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
            logging.error(f"OpenAIError encountered for prompt '{prompt}': {e}")
            return ""
        except Exception as e:
            logging.error(f"Error generating completion for prompt '{prompt}': {e}")
            return ""

    logging.error(f"Failed to generate completion after {retries} attempts for prompt '{prompt}'.")
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

# Process a single entry
def process_entry(entry, output_path, cache):
    namespace = entry.get("namespace")
    prompt = entry.get("prompt")

    if not namespace or not prompt:
        logging.warning(f"Skipping entry due to missing namespace or prompt: {entry}")
        return

    # Check if the result for this namespace already exists in the cache
    if namespace in cache and cache[namespace]:
        logging.info(f"Skipping existing namespace: {namespace}")
        return

    logging.info(f"Processing namespace: {namespace}")

    # Call model to generate code completion
    completion = call_model(prompt)

    # If the completion is empty, do not write to the output file
    if not completion:
        logging.warning(f"No completion generated for namespace: {namespace}. Skipping writing to output.")
        return

    # Update cache
    if "completions" not in cache:
        cache[namespace] = []
    cache[namespace].append(completion)

    # Save the generated result
    result = {
        "namespace": namespace,
        "completions": cache[namespace]
    }

    # Append the result to the output file
    append_to_jsonl_file(output_path, result)

# Main processing function
def process_jsonl_file(input_path, output_path, limit=None):
    # Read input JSONL data
    data = []
    with open(input_path, 'r', encoding='utf-8') as file:
        for line in file:
            data.append(json.loads(line.strip()))

    # Read existing output to build cache
    cache = {}
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as file:
            for line in file:
                entry = json.loads(line.strip())
                namespace = entry.get("namespace")
                completions = entry.get("completions", [])
                if namespace:
                    cache[namespace] = completions

    # If limit is not specified, process all entries
    if limit is None:
        limit = len(data)

    # Process each entry in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [
            executor.submit(process_entry, entry, output_path, cache)
            for entry in data[:limit]
        ]

        # Ensure all tasks are completed
        for future in as_completed(futures):
            try:
                future.result()  # Raise any exceptions here
            except Exception as e:
                logging.error(f"Exception during parallel processing: {e}")

    logging.info(f"Completed processing. Results saved to {output_path}")

if __name__ == "__main__":
    # File pathsl
    input_path = "/home/shixianjie/codegraph/codegraph/DevEval/Experiments/prompt/local_infilling/gpt-4-1106_prompt.jsonl"
    output_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/gpt-4o/infilling_completions.jsonl"

    # Process JSONL file, specifying no limit to process all entries
    process_jsonl_file(input_path, output_path, limit=None)