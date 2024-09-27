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
    # find_one_hop_call_nodes
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
        f'''
You are currently trying to complete the function `{function}` in a code repository.

The namespace of this function in the code repository if {function_namespace}

You can retrieve some context about the function using the available tools. Analyze this context carefully.

1. If you are **fully confident** that the information you now have is enough to complete the function:
    Complete the function:
    {function}:
    

2. If you are **not fully confident** yet, continue to use tools like `get_context_above`, `get_context_below`, `get_import_statements`, and others to gather more context.

3. Make sure to only give me the code , no other informations.

Your decision should be based on whether the gathered information is sufficient to generate a function that integrates seamlessly with the rest of the code in the repository.
'''
    )]
}



# Execute the graph agent and stream results
with tracing_v2_enabled(project_name="tool-user"):
    print_stream(graph.stream(inputs, config=config, stream_mode="values"))
