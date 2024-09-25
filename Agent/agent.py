
import getpass
import os
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tool import find_anchors , get_related_node
from langchain_core.tracers.context import tracing_v2_enabled

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("LANGCHAIN_API_KEY")
_set_env("LANGCHAIN_TRACING_V2")
_set_env("OPENAI_API_KEY")
# First we initialize the model we want to use.
model = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=500)
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
            
            
config = {"configurable": {"thread_id": "1"} }
inputs = {"messages": [("user", 
                        '''
You are currently trying to complete the function `stellar.stellar.app.Stellar.load_config` in the repository code graph.

You have already retrieved some context about the function using the `find_anchors` tool. Analyze this context carefully.

1. If you are **fully confident** that the information you now have is enough to generate the function:
   - Generate the function:
     ```
     def load_config(self):
         <complete the function based on the context>
     ```

2. If you are **not fully confident** yet, continue to use the `find_anchors` tool to gather more context.

Your decision should be based on whether the gathered information is sufficient to generate a function that integrates seamlessly with the rest of the code in the repository.

                        '''
                        )]}

with tracing_v2_enabled(project_name="tool-user"):
    print_stream(graph.stream(inputs, config=config, stream_mode="values"))