import json
import os
from openai import OpenAI
import getpass

# 设置 OpenAI API 密钥
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("OPENAI_API_KEY")


client = OpenAI()
RESULTDIR = "results"

# 检查结果目录是否存在
if not os.path.exists(RESULTDIR):
    os.makedirs(RESULTDIR)

# 读取社区信息的 JSON 文件
def load_community_info(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# 定义为每个社区生成描述的函数
def generate_description_for_community(community_id, community_info):
    try:
        # 准备社区的信息作为输入
        community_nodes = community_info["nodes"]
        community_description = f"Community {community_id} has the following nodes:\n" + "\n".join(
            [f"Node ID: {node['id']}, Label: {node['attributes']['label']}, Type: {node['attributes']['type']}, Signature: {node['attributes']['signature']}" for node in community_nodes]
        )

        # 定义 prompt
        prompt = f'''
            For the code community described below, please generate a concise description that includes:
            1. The specific problem or requirement that this code community addresses.
            2. Key functionalities or features provided by this code, only list out signatures instead of implementation details , as concise as possible.
            3. how other parts of the code graph may interact with this code community.
            your description should no longer than 3 sentences.
            The community information is as follows:
            {community_description}
        '''

        # 调用 OpenAI API 生成结果
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": " You are a professional code consultant. You will help me understand the community structure of my repository code graph."},
                {"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content # 提取返回的内容

    except Exception as e:
        print(f"Error generating description for community {community_id}: {e}")
        return None

# 循环处理多个社区（非并行）
def process_communities(communities):
    results = {}

    # 顺序处理每个社区
    for community_id, info in communities.items():
        description = generate_description_for_community(community_id, info)
        if description is not None:
            results[community_id] = description

    return results

# 将生成的描述保存到新的 JSON 文件中
def save_descriptions_to_json(results, filename=f"{RESULTDIR}/community_descriptions.json"):
    with open(filename, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

def main():
    # 读取社区信息
    communities = load_community_info(f"{RESULTDIR}/community_info.json")

    # 顺序处理每个社区生成描述
    descriptions = process_communities(communities)

    # 保存结果到 JSON 文件
    save_descriptions_to_json(descriptions)

if __name__ == "__main__":
    main()
