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
        "You are a professional code consultant. You will help me understand the community structure "
        "of my repository code graph and assist in completing code functions with context-based information."
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
    with tracing_v2_enabled(project_name="tool-user"):
        # print_stream(graph_agent.stream(inputs, config=config, stream_mode="values"))
         agent_output = list(graph_agent.stream(inputs, config=config, stream_mode="values"))[-1]["messages"][-1].content.strip()

    return agent_output
if __name__ == "__main__":
    # Define the namespace and prompt (for example)

    target_node_label = "mistune.mistune.src.mistune.toc.add_toc_hook"
    prompt ="Your task is to complete the function `add_toc_hook` in a code repository.\n\n    - **Namespace**: `mistune.mistune.src.mistune.toc.add_toc_hook`\n    - **Function signature**:\n    ```python\n    def add_toc_hook(md, min_level=1, max_level=3, heading_id=None):\n\n    \"\"\"\n    This function adds a hook to save table of contents (TOC) items into the state.env. It is usually helpful for doc generator.\n    Input-Output Arguments\n    :param md: Markdown instance. The instance of the Markdown class.\n    :param min_level: Integer. The minimum heading level to include in the TOC.\n    :param max_level: Integer. The maximum heading level to include in the TOC.\n    :param heading_id: Function. A function to generate heading_id.\n    :return: No return values.\n    \"\"\"\n    ```\n\n    You can use the following tools to gather the necessary context before completing the function:\n    - **`get_context_above`**: Fetch code context above the function.\n    - **`get_context_below`**: Fetch code context below the function.\n    - **`get_import_statements`**: Retrieve module import statements.\n    - **`find_one_hop_call_nodes`**: Find related function call nodes.\n    - **`get_node_info`**: Get detailed information about any node in the graph.\n\n    These tools can be applied to the current function or any other nodes you find in the process to gather necessary information.\n\n    Once you have gathered enough information, complete the function and return **only the function's code**.\n\n    Ensure the response contains only the complete code for the function, formatted correctly for the repository."
    graph_name = "mistune"  # Dynamically determined from project path

    # Run the agent for the given entry
    output = run_agent_for_entry(target_node_label , prompt, graph_name)
    print(output)