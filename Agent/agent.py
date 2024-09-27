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
    find_one_hop_call_nodes
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
model = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=500)

# Define tools as individual functions instead of find_anchors.
tools = [
    get_context_above,
    get_context_below,
    get_import_statements,
    get_involved_names,
    find_one_hop_call_nodes
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
function_namespace = 'stellar.stellar.config.save_config'
function = 'def save_config(config):'
nodelimit = 3
# deveval input_code
 
inputs = {
    "messages": [(
        "user",
         "You are tasked with completing the function `_compute_word_freq` in a code repository. \n\n    Here are the key details of this function:\n    - **Namespace**: `sumy.summarizers.sum_basic.SumBasicSummarizer._compute_word_freq`\n    - **Function signature**:\n    ```python\n        def _compute_word_freq(list_of_words):\n\n        \"\"\"\n        This function computes the frequency of each word in the given list of words and returns a dictionary containing the word frequencies.\n        Input-Output Arguments\n        :param list_of_words: List of strings. The list of words for which the frequency needs to be computed.\n        :return: Dictionary. A dictionary containing the frequency of each word in the input list.\n        \"\"\"\n    ```\n\n    You can retrieve some context about the function using the available tools to gather additional information.\n\n    ### Step-by-step process:\n    1. **Analyze the Current Information**:\n        - If you are fully confident that the information currently available (function signature and namespace) is **enough** to complete the function, **directly complete the function**.\n        \n        Complete the function:\n        ```python\n        _compute_word_freq:\n        ```\n\n    2. **Gather Additional Information (if needed)**:\n        - If you are **not fully confident**, you can use the following tools to gather more context:\n          - **`get_context_above`**: Use this tool to get the code context above the current function.\n          - **`get_context_below`**: Use this tool to retrieve the code context below the function.\n          - **`get_import_statements`**: Retrieve the import statements of the module where the function is located.\n          - **`find_one_hop_call_nodes`**: This tool can be used to identify related function nodes by finding one-hop call relationships.\n\n    3. **Call Limit for Tools**:\n        - **Important**: You can only call each tool **up to 10 times** before you must decide whether you have enough information to complete the function.\n\n    ### Important Notes:\n    - Make sure to **only return the complete function's code**.\n    - Use the tools wisely to gather the most relevant information before making a decision to complete the function.\n    - The final goal is to complete a function that seamlessly integrates into the code repository."
    )]
}



# Execute the graph agent and stream results
with tracing_v2_enabled(project_name="tool-user"):
    print_stream(graph.stream(inputs, config=config, stream_mode="values"))
