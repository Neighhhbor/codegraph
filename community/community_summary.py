import json
import os
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

from openai import OpenAI
import getpass

# 设置 OpenAI API 密钥
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("OPENAI_API_KEY")

client = OpenAI()
RESULTDIR = "results"
ALGORITHMS = ["infomap", "leiden", "louvain", "label propagation", "walktrap"]

# 检查结果目录是否存在
if not os.path.exists(RESULTDIR):
    os.makedirs(RESULTDIR)

# 读取社区信息的 JSON 文件
def load_community_info(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# 为每个社区生成描述的函数
def generate_description_for_community(community_id, community_info):
    try:
        community_nodes = community_info["nodes"]
        community_description = f"Community has the following nodes:\n" + "\n".join(
            [f"Label: {node['attributes'].get('label', 'N/A')}, Type: {node['attributes'].get('type', 'N/A')}, Code: {node['attributes'].get('code', 'N/A')}" for node in community_nodes]
        )

        prompt = f'''
            For the code community described below, please generate a concise summary that includes:
            The specific problem or requirement that this code community addresses.
            Your description should be in one sentence.
            The community information is as follows:
            {community_description}
        '''

        # 调用 OpenAI API 生成结果
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional code consultant. You will help me understand the community structure of my repository code graph by generating code summary."},
                {"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating description for community {community_id}: {e}")
        return None

# 处理多个社区（非并行）
def process_communities(communities):
    results = {}
    for community_id, info in communities.items():
        description = generate_description_for_community(community_id, info)
        if description is not None:
            results[community_id] = description
    return results

# 将生成的描述保存到 JSON 文件中
def save_descriptions_to_json(results, filename):
    with open(filename, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

def generate_summary_for_all_algorithms():
    """为每种算法的结果生成代码摘要"""
    for algorithm_name in ALGORITHMS:
        try:
            # 加载每种算法的社区信息
            input_filename = os.path.join(RESULTDIR, f"community_info_{algorithm_name}.json")
            if not os.path.exists(input_filename):
                print(f"File {input_filename} not found. Skipping {algorithm_name}.")
                continue

            communities = load_community_info(input_filename)
            print(f"Generating summaries for {algorithm_name}...")

            # 生成摘要
            descriptions = process_communities(communities)

            # 保存摘要到对应的 JSON 文件
            output_filename = os.path.join(RESULTDIR, f"community_descriptions_{algorithm_name}.json")
            save_descriptions_to_json(descriptions, output_filename)
            print(f"Saved descriptions to {output_filename}")

        except Exception as e:
            print(f"Error processing {algorithm_name}: {e}")

if __name__ == "__main__":
    generate_summary_for_all_algorithms()
