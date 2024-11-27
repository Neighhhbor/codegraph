import os
os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAIError
import random
from agent import run_agent_for_entry
from key import KEYS

API_KEYS = KEYS
PROMPT_FILE = "./prompt_require.jsonl"
OUTPUT_FILE = "./result_v2/completions.jsonl"

def read_prompts_from_jsonl(file_path, max_entries=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data = [json.loads(line.strip()) for line in lines]

    if max_entries:
        data = data[:max_entries]

    return data

def load_existing_completions(file_path):
    if not os.path.exists(file_path):
        return set()

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    existing_namespaces = {json.loads(line.strip()).get("namespace") for line in lines if line.strip()}
    return existing_namespaces

def write_output_to_jsonl(output_data, file_path):
    with open(file_path, 'a', encoding='utf-8') as f:
        for entry in output_data:
            f.write(json.dumps(entry) + '\n')

def clean_code_markdown(md_content):
    clean_code = re.sub(r'```python\n(.*?)\n```', r'\1', md_content, flags=re.DOTALL)
    return clean_code.strip()

def process_single_entry(entry, existing_namespaces, api_key, retries=3):
    namespace = entry.get("namespace")
    prompt = entry.get("prompt")

    if not namespace or not prompt:
        return None, f"Skipping entry: Missing namespace or prompt."
    if namespace in existing_namespaces:
        return None, f"Skipping entry: Namespace {namespace} already has a completion."

    print(f"Running agent for namespace: {namespace} with API key...")

    for attempt in range(1, retries + 1):
        try:
            completion = run_agent_for_entry(prompt, api_key)
            clean_completion = clean_code_markdown(completion)
            if not clean_completion.strip():
                return None, f"Skipping entry: Empty completion for namespace {namespace}."
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

    return None, f"Failed to process {namespace} after {retries} retries."

def generate_agent_outputs_concurrently(data, existing_namespaces, max_workers=8):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for entry in data:
            api_key = API_KEYS[random.randint(0, len(API_KEYS) - 1)]
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
    prompt_data = read_prompts_from_jsonl(PROMPT_FILE)
    existing_namespaces = load_existing_completions(OUTPUT_FILE)
    agent_results = generate_agent_outputs_concurrently(prompt_data, existing_namespaces)
    print(f"Generated {len(agent_results)} new entries and saved to {OUTPUT_FILE}")
    sys.exit(0)
