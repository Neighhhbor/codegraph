import json

def read_jsonl(file_path):
    """
    读取 JSONL 文件并将其解析为 Python 对象列表。
    
    :param file_path: JSONL 文件的路径
    :return: 数据列表，每个元素对应 JSONL 文件中的一行
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            data.append(json.loads(line))
    return data

def generate_prompt(data):
    """
    根据给定的数据字典生成相应的 prompt。
    
    :param data: 包含 namespace, input_code 等关键信息的字典
    :return: 生成的 prompt 字符串
    """
    call_limit = 10
    function_namespace = data.get("namespace", "")
    input_code = data.get("input_code", "")
    function_name = data.get("function_name", "")
    
    prompt = f"""
    You are tasked with completing the function `{function_name}` in a code repository. 

    Here are the key details of this function:
    - **Namespace**: `{function_namespace}`
    - **Function signature**:
    ```python
    {input_code}
    ```

    You can retrieve some context about the function using the available tools to gather additional information.

    ### Step-by-step process:
    1. **Analyze the Current Information**:
        - If you are fully confident that the information currently available (function signature and namespace) is **enough** to complete the function, **directly complete the function**.
        
        Complete the function:
        ```python
        {function_name}:
        ```

    2. **Gather Additional Information (if needed)**:
        - If you are **not fully confident**, you can use the following tools to gather more context:
          - **`get_context_above`**: Use this tool to get the code context above the current function.
          - **`get_context_below`**: Use this tool to retrieve the code context below the function.
          - **`get_import_statements`**: Retrieve the import statements of the module where the function is located.
          - **`find_one_hop_call_nodes`**: This tool can be used to identify related function nodes by finding one-hop call relationships.

    3. **Call Limit for Tools**:
        - **Important**: You can only call each tool **up to {call_limit} times** before you must decide whether you have enough information to complete the function.

    ### Important Notes:
    - Make sure to **only return the complete function's code**.
    - Use the tools wisely to gather the most relevant information before making a decision to complete the function.
    - The final goal is to complete a function that seamlessly integrates into the code repository.
    """
    
    return prompt.strip()

def save_prompts_to_jsonl(prompts, output_file):
    """
    将生成的 prompt 列表保存为 JSONL 文件。
    
    :param prompts: 生成的 prompt 字典列表
    :param output_file: 输出 JSONL 文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as file:
        for prompt in prompts:
            json.dump(prompt, file)
            file.write('\n')

def process_data_and_generate_prompts(input_file, output_file):
    """
    读取 JSONL 文件中的数据，并为每一条数据生成对应的 prompt，然后保存为新的 JSONL 文件。
    
    :param input_file: 输入的 JSONL 文件路径
    :param output_file: 输出的 JSONL 文件路径
    """
    # 读取输入文件
    data_list = read_jsonl(input_file)
    
    # 存储生成的 prompts
    prompts = []
    
    # 为每条数据生成 prompt
    for idx, data in enumerate(data_list):
        prompt_text = generate_prompt(data)  # 生成 prompt
        prompt_data = {
            "namespace": data.get("namespace", ""),
            "prompt": prompt_text,
            # "idx": idx
        }
        prompts.append(prompt_data)
    
    # 保存生成的 prompts 到新的 JSONL 文件
    save_prompts_to_jsonl(prompts, output_file)

# 调用函数，生成所有的 prompts 并保存到 JSONL 文件
input_file_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/Experiments/prompt/LM_prompt_elements.jsonl"  # 替换为你的 JSONL 文件路径
output_file_path = "./prompt.jsonl"  # 替换为你想要保存的 JSONL 文件路径

process_data_and_generate_prompts(input_file_path, output_file_path)
