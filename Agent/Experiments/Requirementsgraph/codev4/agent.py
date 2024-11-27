import os
import json
import getpass
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_core.runnables import RunnableConfig
from tools import duckduckgo_search_tool,format_code_tool, code_search_tool

import os
import time
import logging
from openai import OpenAI, OpenAIError, RateLimitError
import tiktoken  # OpenAI 官方的 token 计数工具

# 定义 GPT 模型的最大 token 限制
MAX_TOKEN_LIMIT = 100000

# 设置 OpenAI API 密钥和基础 URL
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# os.environ['http_proxy'] = "http://127.0.0.1:7890"
# os.environ['https_proxy'] = "http://127.0.0.1:7890"
# os.environ['all_proxy'] = "socks5://127.0.0.1:7890"
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
            
def calculate_token_count(prompt: str, model: str = "gpt-4o") -> int:
    """
    计算给定文本在指定模型下的 token 数量。
    
    Args:
    - prompt (str): 要计算 token 的文本。
    - model (str): OpenAI 模型名称（例如 gpt-4o)

    Returns:
    - token_count (int): 文本对应的 token 数量。
    """
    try:
        # 根据模型加载对应的编码器
        encoding = tiktoken.encoding_for_model(model)
        # 编码文本为 tokens，计算长度
        token_count = len(encoding.encode(prompt))
        return token_count
    except KeyError:
        logging.error(f"Model {model} not supported for token calculation. Falling back to default encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")  # 默认编码器
        return len(encoding.encode(prompt))

def truncate_prompt_to_max_tokens(prompt: str, model: str = "gpt-4o", max_tokens: int = MAX_TOKEN_LIMIT) -> str:
    """
    根据 token 限制截断文本，确保其 token 数量不超过指定上限。
    
    Args:
    - prompt (str): 原始文本。
    - model (str): OpenAI 模型名称（例如 gpt-4）。
    - max_tokens (int): 最大 token 限制。

    Returns:
    - truncated_prompt (str): 截断后的文本。
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(prompt)
    if len(tokens) > max_tokens:
        logging.warning(f"Prompt exceeds {max_tokens} tokens. Truncating to fit within limit.")
        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)
    return prompt


def run_agent_for_entry(prompt: str, api_key: str, retries: int = 5, model_name: str = "gpt-4o") -> str:
    """
    Run the agent for a specific data entry (namespace and prompt) using a specific API key.
    Implements retry logic with exponential backoff for rate limits.
    
    Args:
    - prompt (str): The corresponding prompt for the function.
    - api_key (str): The API key to use for this entry.
    - retries (int): Number of retries for exponential backoff.
    - model_name (str): The model name to use for completions (e.g., gpt-4).
    
    Returns:
    - agent_output (str): The agent's output (completed function code).
    """
    # 设置 API key 环境变量
    os.environ["OPENAI_API_KEY"] = api_key

    # Initialize memory for agent
    memory = MemorySaver()

    # System prompt for the agent
    sys_prompt = (
        "You are an expert python programmer. Pay attention to think step by step and reason yourself to "
        "the correct decisions to ensure accuracy. You need to implement source code based on the following tools."
    )

    # Initialize tools
    tools = [
        duckduckgo_search_tool,
        # code_search_tool,
        format_code_tool
    ]

    # Initialize OpenAI model
    model = ChatOpenAI(model=model_name, temperature=0)

    # Create a graph-based agent
    graph_agent = create_react_agent(model, tools=tools, checkpointer=memory, state_modifier=sys_prompt)

    # Prepare inputs for the agent
    prompt_input = truncate_prompt_to_max_tokens(prompt, model_name, MAX_TOKEN_LIMIT)
    inputs = {
        "messages": [("user", prompt_input)]
    }

    # Define runnable configuration
    config = RunnableConfig({
        "configurable": {"thread_id": "2"},
        "recursion_limit": 25
    })

    # Retry logic with exponential backoff
    wait_time = 1
    for attempt in range(1, retries + 1):
        try:
            # Enable tracing and execute the agent
            with tracing_v2_enabled(project_name="agent"):
                agent_output = list(graph_agent.stream(inputs, config=config, stream_mode="values"))[-1]["messages"][-1].content.strip()

            return agent_output

        except RateLimitError:
            logging.warning(f"Rate limit reached for prompt. Attempt {attempt}/{retries}. Waiting for {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            wait_time *= 2  # Exponential backoff
        except OpenAIError as e:
            logging.error(f"OpenAIError encountered for prompt '{prompt[:100]}': {e}")
            return ""
        except Exception as e:
            logging.error(f"Error generating completion for prompt '{prompt[:100]}': {e}")
            return ""

    logging.error(f"Failed to generate completion after {retries} attempts for prompt '{prompt[:100]}'.")
    return ""



if __name__ == "__main__":
    # Define the namespace and prompt (for example)

    target_node_label = "mistune.toc.add_toc_hook"
    prompt ="Your task is to complete the function `add_toc_hook` in a code repository using a ReAct approach (Reasoning + Acting).\n\n    - **Target code**: `add_toc_hook`\n    - **namespace**: `mistune.toc.add_toc_hook`\n    ```python\n    def add_toc_hook(md, min_level=1, max_level=3, heading_id=None):\n\n    \"\"\"\n    This function adds a hook to save table of contents (TOC) items into the state.env. It is usually helpful for doc generator.\n    Input-Output Arguments\n    :param md: Markdown instance. The instance of the Markdown class.\n    :param min_level: Integer. The minimum heading level to include in the TOC.\n    :param max_level: Integer. The maximum heading level to include in the TOC.\n    :param heading_id: Function. A function to generate heading_id.\n    :return: No return values.\n    \"\"\"\n    ```\n\n    ### Instructions:\n\n    1. **Preliminary Research**:\n        - Start by using the `duckduckgo_search_tool` to gather any contextual information that might help understand the purpose or domain-specific usage of `add_toc_hook`.\n        - Based on the search results, reason whether you need additional context from the codebase before proceeding.\n\n    2. **Relative Code Retrieval**:\n        - Use the `code_search_tool` to retrieve related code for the target `mistune.toc.add_toc_hook` based on three requirements:\n        - **Child Requirement**: Code that directly depends on or extends the target `mistune.toc.add_toc_hook`.\n        - **Context Requirement**: Code that shares the same context or interacts closely with `mistune.toc.add_toc_hook`.\n        - **Similarity Requirement**: Code that has similar functionality or structure to `mistune.toc.add_toc_hook`.\n        - The input for this tool must be the exact namespace, not the function name.\n        - Based on the retrieved results from the three categories, identify the most relevant pieces of code to inform how `mistune.toc.add_toc_hook` should be implemented.\n\n    3. **Formatting**:\n        - After completing the function, use the `format_code_tool` to format the code using Black, ensuring it adheres to Python standards.    \n        \n    4. **Function Completion**:\n        - Once you have gathered enough information and context, proceed to complete the function in the following format:\n        - Your final output should be the fully completed function code. \n        - DO NOT include any additional descriptions in the output , even if some tool fail to gather information.\n        ```python\n        <completed code>\n        ```"
    # Run the agent for the given entry
    apikey = "sk-JFdL055uB2VYCYa5D0188d959b294bC9BdE75c44F930CcC9"
    output = run_agent_for_entry(prompt,apikey)
    print(output)
