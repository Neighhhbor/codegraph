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
    input_code = data.get("input_code", "")
    function_name = data.get("function_name", "")
    
    prompt = f"""
    Your task is to complete the function `{function_name}` in a code repository using a ReAct approach (Reasoning + Acting).

    - **Target Node Name**: `{target_function_node}`
    - **Function Signature**:
    ```python
    {input_code}
    ```

    ### Instructions:

    1. **Preliminary Research**:
        - Start by using the `duckduckgo_search_tool` to gather any contextual information that might help understand the purpose or domain-specific usage of `{function_name}`.
        - Based on the search results, reason whether you need additional context from the codebase before proceeding.

    2. **Contextual Code Retrieval**:
        - After gathering preliminary research, use the following tools in the given order to gather context related to the target function:
        
        - **`get_context_above_tool`**: Retrieves the code immediately above the target function.
        
        - **`get_context_below_tool`**: Retrieves the code immediately following the target function.
        
        - **`get_import_statements_tool`**: Extracts all import statements in the current module.
        
        - **`get_involved_names_tool`**: Identifies all relevant names (classes, variables, etc.) that are involved around `{target_function_node}`.

    3. **Additional Node Exploration**:
        - If more information is needed about how the target function interacts with other parts of the codebase, use the following tools:
        
        - **`find_one_hop_call_nodes_tool`**: Identifies functions directly calling or being called by the target function.
        
        - **`get_node_info_tool`**: Retrieves detailed information about specific nodes identified in previous steps.

        - You can use these tools multiple times if necessary, targeting different nodes to gather comprehensive information.

    4. **Reasoning and Acting Process**:
        - Before proceeding to complete the function, make sure you have gathered all necessary context and information.
        
        - Continuously assess whether the gathered information is sufficient to proceed with function completion. If not, use the tools again to gather more information.
        
        - Do not proceed to function completion until you are confident that you have all relevant context and information.

    5. **Function Completion**:
        - Once you have gathered enough information and context, proceed to complete the function in the following format:
        ```python
        def {function_name}(...):
            # complete code
        ```

    6. **Formatting**:
        - After completing the function, use the `format_code_tool` to format the code using Black, ensuring it adheres to Python standards.

    7. **Final Output**:
        - Your final output should be the fully completed and formatted function code. Do not include any additional information, comments, or descriptions in the output.
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
