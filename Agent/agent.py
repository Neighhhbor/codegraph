
import getpass
import os
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tool import find_anchors , get_related_node


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("OPENAI_API_KEY")

# First we initialize the model we want to use.
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
tools = [find_anchors , get_related_node]

# We can add "chat memory" to the graph with LangGraph's checkpointer
# to retain the chat context between interactions
memory = MemorySaver()
# system prompt
sys_prompt = "You are a professional code consultant. You will help me understand the community structure of my repository code graph."
# Define the graph
graph = create_react_agent(model, tools=tools, checkpointer=memory,state_modifier=sys_prompt)

def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()
            
            
config = {"configurable": {"thread_id": "1"}}
inputs = {"messages": [("user", "call find_anchors('import') and 5 more times with random args")]}

print_stream(graph.stream(inputs, config=config, stream_mode="values"))