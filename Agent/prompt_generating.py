import json
import os

def read_jsonl(file_path):
    """
    读取 JSONL 文件并将其解析为 Python 对象列表。
    
    :param file_path: JSONL 文件的路径
    :return: 数据列表，每个元素对应 JSONL 文件中的一行
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                data.append(json.loads(line.strip()))  # 读取每一行，并解析为 JSON 对象
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e} in line: {line.strip()}")
    return data

def transform_completion_path(completion_path):
    """
    转换 `completion_path` 为符合 Python 导入规则的路径。
    去掉类别部分，并将 `/` 替换为 `.`。
    
    :param completion_path: 文件路径，如 `Text-Processing/xmnlp/xmnlp/utils/__init__.py`
    :return: 转换后的路径，如 `xmnlp.xmnlp.utils.__init__`
    """
    # 去掉最前面的类别部分 (Text-Processing)，然后去掉文件扩展名 `.py`
    path_without_category = "/".join(completion_path.split('/')[1:])  # 去掉第一部分
    path_without_extension = path_without_category.replace('.py', '')
    
    # 将路径中的 `/` 替换为 `.` 来表示 Python 导入路径
    transformed_path = path_without_extension.replace('/', '.')
    
    return transformed_path

def generate_prompt(data, target_function_node):
    """
    根据给定的数据字典生成相应的 prompt。
    
    :param data: 包含 namespace, input_code 等关键信息的字典
    :param target_function_node: 真实节点名，即 `transformed_path.namespace`
    :return: 生成的 prompt 字符串
    """
    input_code = data.get("input_code", "")
    function_name = data.get("function_name", "")
    
    prompt = f"""
    Your task is to complete the function `{function_name}` in a code repository.

    - **Target Node Name**: `{target_function_node}`
    - **Function signature**:
    ```python
    {input_code}
    ```

    ### Instructions:

    1. **Attempt to Complete the Function**:
        - If the current information (function signature and target node name) provides enough context to confidently complete the function, proceed and complete it directly without further investigation.

        Complete the function in the following format:
        ```python
        def {function_name}(...):
            # complete code
        ```

    2. **Use Tools to Gather Additional Information (If Needed)**:
        - If the provided information is not enough, use the available tools to gather more context from the code repository graph. These tools will help you fetch relevant parts of the code and its dependencies:

        - **`get_context_above`**: This tool retrieves the code immediately above the target function in the same file/module. Use it to understand preceding definitions or the function's environment.
        
        - **`get_context_below`**: This tool retrieves the code immediately following the target function. This could provide insights into subsequent definitions or references to the function.
        
        - **`get_import_statements`**: Use this tool to extract all the import statements in the current module. This will help you understand external dependencies or libraries required by the function.
        
        - **`find_one_hop_call_nodes`**: This tool identifies functions directly calling or being called by the target function within the code graph. It helps to see how the target function is connected to others.
        
        - **`get_node_info`**: Retrieve detailed information (such as attributes or metadata) about any specific node in the code graph, including the target function itself, to gain a deeper understanding of its role.

    3. **Key Objective**:
        - Your goal is to gather enough information using the tools provided to fully understand the code repository and confidently complete the target function.
        - **Do not output any explanation or natural language description**. Only return the complete code for the function in a well-formatted Python syntax.
    
    4. **Final Output**:
        - Ensure that you **only return the fully completed function** as your final output, without any additional information, comments, or descriptions.
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

def process_data_and_generate_prompts(input_file, data_json_file, output_file):
    """
    读取 JSONL 文件中的数据，并为每一条数据生成对应的 prompt，然后保存为新的 JSONL 文件。
    
    :param input_file: 输入的 JSONL 文件路径
    :param data_json_file: 存储每条数据的图信息的 JSON 文件路径
    :param output_file: 输出的 JSONL 文件路径
    """
    # 读取输入文件
    data_list = read_jsonl(input_file)
    
    # 读取 data.jsonl 文件中的项，获取 project_path
    project_data = read_jsonl(data_json_file)

    # 存储生成的 prompts
    prompts = []
    
    # 为每条数据生成 prompt
    for idx, data in enumerate(data_list):
        raw_namespace = data.get("namespace", "")
        
        # 根据 data.jsonl 获取 graph_name 和 completion_path
        project_info = next((proj for proj in project_data if proj["namespace"] == raw_namespace), None)
        if project_info:
            completion_path = project_info.get("completion_path", "")
        else:
            print(f"No project found for namespace: {raw_namespace}")
            continue
        
        # 生成真实的 target_function_node
        transformed_path = transform_completion_path(completion_path)
        target_function_node = f"{transformed_path}.{raw_namespace.split('.')[-1]}"
        
        # 生成 prompt
        prompt_text = generate_prompt(data, target_function_node)
        
        prompt_data = {
            "namespace": raw_namespace,
            "target_function_node_label": target_function_node ,  # 添加真实的 target_function_node_label 字段
            "prompt": prompt_text,
        }
        prompts.append(prompt_data)
    
    # 保存生成的 prompts 到新的 JSONL 文件
    save_prompts_to_jsonl(prompts, output_file)

# 调用函数，生成所有的 prompts 并保存到 JSONL 文件
input_file_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/Experiments/prompt/LM_prompt_elements.jsonl"  # 替换为你的 JSONL 文件路径
data_json_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/data.jsonl"  # 替换为包含项目路径的 data.jsonl 文件路径
output_file_path = "./prompt.jsonl"  # 替换为你想要保存的 JSONL 文件路径

process_data_and_generate_prompts(input_file_path, data_json_path, output_file_path)
