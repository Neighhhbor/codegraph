import json
import os
from langchain_openai import ChatOpenAI
from langchain_community.llms import Tongyi
from langchain_core.messages import HumanMessage
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
os.environ["DASHSCOPE_API_KEY"] = "sk-13c3d5c92dbc45c7a5422095efa61353"

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())
DASHSCOPE_API_KEY=os.environ["DASHSCOPE_API_KEY"]

#使用通义千问
model = Tongyi()

RESULTDIR = "results"

# 检查结果目录是否存在
if not os.path.exists(RESULTDIR):
    os.makedirs(RESULTDIR)

# 读取社区信息的 JSON 文件
def load_community_info(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# 定义为每个社区生成描述的 langchain pipeline
def generate_description_for_community(community_id, community_info):
    try:
        # 定义 prompt 模板
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    '''You are a professional code consultant. For the code community described below, please generate a detailed description that includes:
                        1. The specific problem or requirement that this code addresses.
                        2. Key functionalities or features provided by this code.
                        3. Potential modules or sections of a larger project that may utilize this code.

                        The community information is as follows:
                    ''',
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # 准备社区的信息作为输入
        community_nodes = community_info["nodes"]
        community_description = f"Community {community_id} has the following nodes:\n" + "\n".join(
            [f"Node ID: {node['id']}, Label: {node['attributes']['label']}, Type: {node['attributes']['type']}, Code: {node['attributes']['code']}" for node in community_nodes]
        )

        # 将信息放入 `messages` 变量
        inputs = {
            "messages": [HumanMessage(content=community_description)]
        }

        # 执行管道并生成结果
        chain = prompt | model
        output = chain.invoke(inputs)

        return output

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
        json.dump(results, f, indent=4)

def main():
    # 读取社区信息
    communities = load_community_info(f"{RESULTDIR}/community_info.json")

    # 顺序处理每个社区生成描述
    descriptions = process_communities(communities)

    # 保存结果到 JSON 文件
    save_descriptions_to_json(descriptions)

if __name__ == "__main__":
    main()