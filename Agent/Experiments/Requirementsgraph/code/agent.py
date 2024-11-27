import os
import json
import getpass
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_core.runnables import RunnableConfig
from tools import duckduckgo_search_tool, get_relative_code, format_code_tool


# 定义 API keys 列
# 设置 OpenAI API 密钥和基础 URL
os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"


# Helper function to set environment variables
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# Set environment variables for API keys
_set_env("LANGCHAIN_API_KEY")
_set_env("LANGCHAIN_TRACING_V2")
_set_env("RIZA_API_KEY")



# Function to print the stream of messages
def print_stream(stream):
    if not stream:
        print("No data returned from the stream.")
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()

# Encapsulate the agent process into a function
# Encapsulate the agent process into a function
def run_agent_for_entry(prompt: str, api_key: str):
    """
    Run the agent for a specific data entry (namespace and prompt) using a specific API key.
    
    Args:
    - prompt (str): The corresponding prompt for the function.
    - api_key (str): The API key to use for this entry.
    
    Returns:
    - agent_output (str): The agent's output (completed function code).
    """
    # 设置 API key 环境变量
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = "https://api.yesapikey.com/v1"
    # Create a new instance of the agent
    memory = MemorySaver()

    sys_prompt = (
       "You are an expert python programmer, pay attention to think step by step and reason yourself to the correct decisions to make sure we get it right. You need to implement source code based on the following tools."
    )

    # 创建工具并处理图数据
    tools = [
        duckduckgo_search_tool,
        get_relative_code,
        format_code_tool
    ]
    # Initialize the model to use
    model = ChatOpenAI(model="gpt-4o", temperature=0)

    graph_agent = create_react_agent(model, tools=tools, checkpointer=memory, state_modifier=sys_prompt)

    # Prepare inputs for the agent
    inputs = {
        "messages": [(
            "user", prompt
        )]
    }

    # Define the config
    config = RunnableConfig({
        "configurable": {"thread_id": "2"},
        "recursion_limit": 25
    })

    # Execute the graph agent and capture results
    with tracing_v2_enabled(project_name="codeagent"):
        agent_output = list(graph_agent.stream(inputs, config=config, stream_mode="values"))[-1]["messages"][-1].content.strip()

    return agent_output

if __name__ == "__main__":
    # Define the namespace and prompt (for example)

    target_node_label = "mistune.src.mistune.toc.add_toc_hook"
    prompt ="Your task is to complete the function `add_toc_hook` in a code repository using a ReAct approach (Reasoning + Acting).\n\n    - **Target code**: `add_toc_hook`\n    - **Function Signature**:\n    ```python\n    def add_toc_hook(md, min_level=1, max_level=3, heading_id=None):\n\n    \"\"\"\n    This function adds a hook to save table of contents (TOC) items into the state.env. It is usually helpful for doc generator.\n    Input-Output Arguments\n    :param md: Markdown instance. The instance of the Markdown class.\n    :param min_level: Integer. The minimum heading level to include in the TOC.\n    :param max_level: Integer. The maximum heading level to include in the TOC.\n    :param heading_id: Function. A function to generate heading_id.\n    :return: No return values.\n    \"\"\"\n    ```\n\n    ### Instructions:\n\n    1. **Preliminary Research**:\n        - Start by using the `duckduckgo_search_tool` to gather any contextual information that might help understand the purpose or domain-specific usage of `add_toc_hook`.\n        - Based on the search results, reason whether you need additional context from the codebase before proceeding.\n\n    2. **Similar Code Retrieval**:\n        - After gathering preliminary research, use the following tools in the given order to gather context related to the target function:\n            - Use the `bm25_search_tool` to locate the top 5 functions or classes in the codebase that have the most similar names or functionality to `add_toc_hook`.\n            - Based on the bm25 results, identify the most relevant function or class to inform how `add_toc_hook` should be implemented.\n            - Use `find_most_similar_function_tool` if necessary to locate the most closely related function for detailed comparison.\n\n    3. **Formatting**:\n        - After completing the function, use the `format_code_tool` to format the code using Black, ensuring it adheres to Python standards.    \n        \n    4. **Function Completion**:\n        - Once you have gathered enough information and context, proceed to complete the function in the following format:\n        - Your final output should be the fully completed function code. DO NOT include any additional descriptions in the output.\n        ```python\n            # completed code\n        ```"
    # Run the agent for the given entry
    output = run_agent_for_entry(prompt)
    print(output)
