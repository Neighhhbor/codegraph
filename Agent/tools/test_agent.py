import os

os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

import json
import getpass
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tools import create_tools
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_core.runnables import RunnableConfig


# Helper function to set environment variables
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# Set environment variables for API keys
_set_env("LANGCHAIN_API_KEY")
_set_env("LANGCHAIN_TRACING_V2")
_set_env("OPENAI_API_KEY")
_set_env("RIZA_API_KEY")

# Initialize the model to use
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 常量：图文件的根目录路径
GRAPH_DIR = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs/"

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
def run_agent_for_entry(target_node_label: str, prompt: str, graph_name: str):
    """
    Run the agent for a specific data entry (namespace and prompt).
    
    Args:
    - namespace (str): The namespace of the function.
    - prompt (str): The corresponding prompt for the function.
    - graph_name (str): The graph name corresponding to the project.
    
    Returns:
    - agent_output (str): The agent's output (completed function code).
    """
    # Create a new instance of the agent
    memory = MemorySaver()

    sys_prompt = (
       "You are an expert python programmer, pay attention to think step by step and reason yourself to the correct decisions to make sure we get it right. You need to implement source code based on the following tools."
    )

    # 动态构建图的路径
    graph_path = os.path.join(GRAPH_DIR, f"{graph_name}.json")
    
    # 创建工具并处理图数据
    tools = create_tools(graph_path, target_node_label)

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
    with tracing_v2_enabled(project_name="pipeline"):
        # print_stream(graph_agent.stream(inputs, config=config, stream_mode="values"))
         agent_output = list(graph_agent.stream(inputs, config=config, stream_mode="values"))[-1]["messages"][-1].content.strip()

    return agent_output
if __name__ == "__main__":
    # Define the namespace and prompt (for example)

    target_node_label = "mistune.src.mistune.toc.add_toc_hook"
    prompt ="Your task is to complete the function `add_toc_hook` in a code repository.\n\n    - **Target Node Name**: `mistune.src.mistune.toc.add_toc_hook`\n    - **Function signature**:\n    ```python\n    def add_toc_hook(md, min_level=1, max_level=3, heading_id=None):\n\n    \"\"\"\n    This function adds a hook to save table of contents (TOC) items into the state.env. It is usually helpful for doc generator.\n    Input-Output Arguments\n    :param md: Markdown instance. The instance of the Markdown class.\n    :param min_level: Integer. The minimum heading level to include in the TOC.\n    :param max_level: Integer. The maximum heading level to include in the TOC.\n    :param heading_id: Function. A function to generate heading_id.\n    :return: No return values.\n    \"\"\"\n    ```\n\n    ### Instructions:\n\n    1. **Use DuckDuckGo for Preliminary Research**:\n        - Use the `duckduckgo_search_tool` with relevant keywords to gather any contextual information that may help in understanding the purpose or domain-specific usage of `add_toc_hook`.\n        \n    2. **Attempt to Complete the Function**:\n        - If the search results and the current information (function signature and target node name) provide enough context, proceed to complete the function without further investigation.\n        \n        Complete the function in the following format:\n        ```python\n        def add_toc_hook(...):\n            # complete code\n        ```\n\n    3. **Use Tools to Gather Additional Information (If Needed)**:\n        - If additional context is still required, use the following tools to gather more information:\n        \n        - **`get_context_above`**: Retrieves the code immediately above the target function in the same file/module.\n        \n        - **`get_context_below`**: Retrieves the code immediately following the target function.\n        \n        - **`get_import_statements`**: Extracts all import statements in the current module.\n        \n        - **`find_one_hop_call_nodes`**: Identifies functions directly calling or being called by the target function within the code graph.\n        \n        - **`get_node_info`**: Retrieves detailed information about any specific node in the code graph.\n        \n    4. **Final Output and Black Code Formatting**:\n        - Once you have completed the function, use the `format_code_tool` to format the code using Black to ensure it adheres to Python standards.\n        \n        - Your final output should be the fully completed and formatted function code, without any additional information, comments, or descriptions."
    graph_name = "mistune"  # Dynamically determined from project path

    # Run the agent for the given entry
    output = run_agent_for_entry(target_node_label , prompt, graph_name)
    print(output)