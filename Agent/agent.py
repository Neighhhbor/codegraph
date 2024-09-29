import getpass
import os
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tool import (
    get_context_above,
    get_context_below,
    get_import_statements,
    get_involved_names,
    find_one_hop_call_nodes,
    get_node_info
)
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

# Initialize the model to use.
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Define tools as individual functions instead of find_anchors.
tools = [
    get_involved_names,
    get_context_above,
    get_context_below,
    get_import_statements,
    find_one_hop_call_nodes,
    get_node_info
]

# Adding "chat memory" to retain chat context across multiple interactions
memory = MemorySaver()

# System prompt for the AI model
sys_prompt = ("You are a professional code consultant. You will help me understand the community structure "
              "of my repository code graph and assist in completing code functions with context-based information.")

# Create the graph agent with the model, tools, and memory
graph = create_react_agent(model, tools=tools, checkpointer=memory, state_modifier=sys_prompt)

# Function to print the stream of messages
def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()

# Configuring the execution limits
config = RunnableConfig({
    "configurable": {"thread_id": "1"},
    "recursion_limit": 25
})

# Define user input prompt
# deveval input_code
 
inputs = {
    "messages": [(
        "user",
"Your task is to complete the function `do_OP_HASH256` in a code repository.\n\n    - **Namespace**: `pycoin.pycoin.satoshi.stackops.do_OP_HASH256`\n    - **Function signature**:\n    ```python\n    def do_OP_HASH256(stack):\n\n    \"\"\"\n    Pop the top item from the stack, calculate its sha256 value, and append the result back to the stack.\n\n    Input-Output Arguments\n    :param stack: List, a stack where the operation is performed.\n    :return: No return values.\n\n    \"\"\"\n    ```\n\n    You can use the following tools to gather the necessary context before completing the function:\n    - **`get_context_above`**: Fetch code context above the function.\n    - **`get_context_below`**: Fetch code context below the function.\n    - **`get_import_statements`**: Retrieve module import statements.\n    - **`find_one_hop_call_nodes`**: Find related function call nodes.\n    - **`get_node_info`**: Get detailed information about any node in the graph.\n\n    These tools can be applied to the current function or any other nodes you find in the process to gather necessary information.\n\n    Once you have gathered enough information, complete the function and return **only the function's code**.\n\n    Ensure the response contains only the complete code for the function, formatted correctly for the repository."
       )]
}



# Execute the graph agent and stream results
with tracing_v2_enabled(project_name="tool-user"):
    print_stream(graph.stream(inputs, config=config, stream_mode="values"))
