import json
import os
from tqdm import tqdm  # 引入 tqdm 用于显示进度条

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

def generate_prompt(data):
    
    input_code = data.get("input_code", "")
    function_name = data.get("function_name", "")
    namespace = data.get("namespace")
    prompt = f"""
    Your task is to complete the function `{function_name}` in a code repository using a ReAct approach (Reasoning + Acting).

    - **Target code**: `{function_name}`
    - **namespace**: `{namespace}`
    ```python
    {input_code}
    ```

    ### Instructions:

    1. **Preliminary Research**:
        - Start by using the `duckduckgo_search_tool` to gather any contextual information that might help understand the purpose or domain-specific usage of `{function_name}`.
        - Based on the search results, reason whether you need additional context from the codebase before proceeding.

    2. **Relative Code Retrieval**:
        - Use the `code_search_tool` to retrieve related code for the target `{namespace}` based on three requirements:
        - **Child Requirement**: Code that directly depends on or extends the target `{namespace}`.
        - **Context Requirement**: Code that shares the same context or interacts closely with `{namespace}`.
        - **Similarity Requirement**: Code that has similar functionality or structure to `{namespace}`.
        - The input for this tool must be the exact namespace, not the function name.
        - Based on the retrieved results from the three categories, identify the most relevant pieces of code to inform how `{namespace}` should be implemented.

    3. **Formatting**:
        - After completing the function, use the `format_code_tool` to format the code using Black, ensuring it adheres to Python standards.    
        
    4. **Function Completion**:
        - Once you have gathered enough information and context, proceed to complete the function in the following format:
        - Your final output should be the fully completed function code. 
        - DO NOT include any additional descriptions in the output , even if some tool fail to gather information.
        ```python
        <completed code>
        ```
    """
    return prompt.strip()

def save_prompts_to_jsonl(prompts, output_file):
    """
    将生成的 prompt 列表保存为 JSONL 文件。
    """
    with open(output_file, 'w', encoding='utf-8') as file:
        for prompt in prompts:
            json.dump(prompt, file)
            file.write('\n')

def process_data_and_generate_prompts(input_file,  output_file):
    """
    读取 JSONL 文件中的数据，并为每一条数据生成对应的 prompt，然后保存为新的 JSONL 文件。
    """
    data_list = read_jsonl(input_file)

    prompts = []
    
    # 使用 tqdm 显示进度条
    for idx, data in enumerate(tqdm(data_list, desc="Processing Data", unit="entry")):
        # 生成 prompt
        prompt_text = generate_prompt(data)
        input_code = data.get("input_code", "")
        function_name = data.get("function_name", "")
        namespace = data.get("namespace")
        prompt_data = {
            "namespace": namespace , 
            "function_name":function_name,
            "input_code":input_code,
            "prompt": prompt_text,
        }
        prompts.append(prompt_data)
    
    # 保存生成的 prompts 到新的 JSONL 文件
    save_prompts_to_jsonl(prompts, output_file)

# 调用函数，生成所有的 prompts 并保存到 JSONL 文件
input_file_path = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/promptelements/LM_prompt_elements_merged.jsonl"
output_file_path = "./prompt.jsonl"

process_data_and_generate_prompts(input_file_path,output_file_path)
