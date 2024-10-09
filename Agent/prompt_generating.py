import json
import os
from difflib import SequenceMatcher
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

def transform_completion_path(completion_path):
    """
    转换 `completion_path` 为符合 Python 导入规则的路径。
    去掉类别部分，并将 `/` 替换为 `.`。
    """
    path_without_category = "/".join(completion_path.split('/')[1:])  # 去掉第一部分
    path_without_extension = path_without_category.replace('.py', '')
    transformed_path = path_without_extension.replace('/', '.')
    return transformed_path

def generate_target_function_node(namespace, transformed_path):
    """
    基于两重循环逐步匹配生成 target_function_node，避免重复部分。
    """
    transformed_parts = transformed_path.split('.')
    namespace_parts = namespace.split('.')

    overlap_length = 0
    for i in range(len(transformed_parts)):
        for j in range(len(namespace_parts)):
            overlap_count = 0
            while (i + overlap_count < len(transformed_parts) and 
                   j + overlap_count < len(namespace_parts) and 
                   transformed_parts[i + overlap_count] == namespace_parts[j + overlap_count]):
                overlap_count += 1
            overlap_length = max(overlap_length, overlap_count)
    
    result_parts = transformed_parts[:overlap_length]
    result_parts.extend(namespace_parts[overlap_length:])
    final_path = '.'.join(result_parts)
    return final_path

def calculate_edit_distance(s1, s2):
    """
    计算字符串之间的编辑距离。
    """
    return SequenceMatcher(None, s1, s2).ratio()

def find_closest_function_node(candidate_node, graph_data):
    """
    查找与候选节点编辑距离最接近的 function 类型的节点。
    """
    closest_node = None
    best_similarity = 0

    for node in graph_data:
        if node.get("type") == "function":
            node_label = node.get("id", "")
            similarity = calculate_edit_distance(candidate_node, node_label)
            if similarity > best_similarity:
                best_similarity = similarity
                closest_node = node_label

    return closest_node if closest_node else candidate_node

def load_graph_data(graph_path):
    """
    加载指定路径下的代码图 JSON 文件，并返回其中的节点列表。
    """
    if not os.path.exists(graph_path):
        print(f"Graph file not found: {graph_path}")
        return []
    
    with open(graph_path, 'r', encoding='utf-8') as file:
        graph_json = json.load(file)
        return graph_json.get("nodes", [])

def check_node_in_graph(candidate_node, graph_data):
    """
    检查候选节点是否存在于图数据的节点列表中。
    """
    return any(item["id"] == candidate_node for item in graph_data if item.get("type") == "function")

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

    5. **Formatting**:
        - After completing the function, use the `format_code_tool` to format the code using Black, ensuring it adheres to Python standards.    
        
    6. **Function Completion**:
        - Once you have gathered enough information and context, proceed to complete the function in the following format:
        - Your final output should be the fully completed function code. DO NOT include any additional descriptions in the output.
        ```python
        def {function_name}(...):
            # completed code
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

def process_data_and_generate_prompts(input_file, data_json_file, graph_directory, output_file):
    """
    读取 JSONL 文件中的数据，并为每一条数据生成对应的 prompt，然后保存为新的 JSONL 文件。
    """
    data_list = read_jsonl(input_file)
    project_data = read_jsonl(data_json_file)

    prompts = []
    
    # 使用 tqdm 显示进度条
    for idx, data in enumerate(tqdm(data_list, desc="Processing Data", unit="entry")):
        raw_namespace = data.get("namespace", "")
        
        project_info = next((proj for proj in project_data if proj["namespace"] == raw_namespace), None)
        if project_info:
            completion_path = project_info.get("completion_path", "")
        else:
            print(f"No project found for namespace: {raw_namespace}")
            continue
        
        # 生成初步的 target_function_node
        transformed_path = transform_completion_path(completion_path)
        candidate_node = generate_target_function_node(raw_namespace, transformed_path)
        
        # 加载对应的代码图
        graph_name = transformed_path.split('.')[0]  # 获取代码图的名称
        graph_path = os.path.join(graph_directory, f"{graph_name}.json")
        graph_data = load_graph_data(graph_path)
        
        # 检查 candidate_node 是否存在于图中
        if not check_node_in_graph(candidate_node, graph_data):
            # 如果不存在，查找编辑距离最小的函数节点
            candidate_node = find_closest_function_node(candidate_node, graph_data)
        
        # 生成 prompt
        prompt_text = generate_prompt(data, candidate_node)
        
        prompt_data = {
            "namespace": raw_namespace,
            "target_function_node_label": candidate_node,
            "prompt": prompt_text,
        }
        prompts.append(prompt_data)
    
    # 保存生成的 prompts 到新的 JSONL 文件
    save_prompts_to_jsonl(prompts, output_file)

# 调用函数，生成所有的 prompts 并保存到 JSONL 文件
input_file_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/Experiments/prompt/LM_prompt_elements.jsonl"
data_json_path = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/data.jsonl"
graph_directory = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs"
output_file_path = "./prompt.jsonl"

process_data_and_generate_prompts(input_file_path, data_json_path, graph_directory, output_file_path)
