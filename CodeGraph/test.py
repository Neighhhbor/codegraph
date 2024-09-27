import json
import os
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置 API 密钥和基础 URL
os.environ["DASHSCOPE_API_KEY"] = "sk-13c3d5c92dbc45c7a5422095efa61353"

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

RESULTDIR = "results"

# 读取社区信息的 JSON 文件
def load_community_info(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# 定义为每个社区生成描述的函数
def generate_description_for_community(community_id, community_info):
    # 准备社区的信息作为输入
    community_nodes = community_info["nodes"]
    community_description = f"Community {community_id} has the following nodes:\n" + "\n".join(
        [f"Node ID: {node['id']}, Attributes: {node['attributes']}" for node in community_nodes]
    )

    # 调用 DashScope API 生成描述
    completion = client.chat.completions.create(
        model="qwen-turbo",
        messages=[
            {'role': 'system', 'content': 'You are a professional code consultant. You will generate descriptions for the code community below to help me understand the code snippets.'},
            {'role': 'user', 'content': community_description}
        ]
    )

    return completion['choices'][0]['message']['content']

# 并行处理多个社区
def process_communities_parallel(communities, max_workers=4):
    results = {}

    # 使用 ThreadPoolExecutor 来并行处理社区
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(generate_description_for_community, community_id, info): community_id
            for community_id, info in communities.items()
        }

        for future in as_completed(futures):
            community_id = futures[future]
            try:
                description = future.result()
                results[community_id] = description
            except Exception as exc:
                print(f"Community {community_id} generated an exception: {exc}")

    return results

# 将生成的描述保存到新的 JSON 文件中
def save_descriptions_to_json(results, filename=f"{RESULTDIR}/community_descriptions.json"):
    with open(filename, 'w') as f:
        json.dump(results, f, indent=4)

def main():
    # 读取社区信息
    communities = load_community_info(f"{RESULTDIR}/community_info.json")
    
    # 并行处理每个社区生成描述
    descriptions = process_communities_parallel(communities, max_workers=4)
    
    # 保存结果到 JSON 文件
    save_descriptions_to_json(descriptions)

if __name__ == "__main__":
    main()
