import os
import sys
import time
from tqdm import tqdm
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import torch
import torch.nn as nn
import psutil
import socket

# 设置可见的 CUDA 设备为 2 和 3
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
# 设置 HuggingFace 镜像站点
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# 使用相对路径添加项目根目录到 Python 搜索路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

import networkx as nx
import json
from typing import List, Dict, Any
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
import black


BM25_SEARCH_FILE = "./bm25_retrieved.jsonl"
 # 新增 DuckDuckGo 搜索工具
@tool
def duckduckgo_search_tool(query: str) -> str: 
    """
    Perform a web search using DuckDuckGo and summarize the results.
    :param query: The search query
    :return: A summary of the search results
    """
    search = DuckDuckGoSearchRun()
    # llm = ChatOpenAI(model_name="gpt-4o", temperature=0)  # Use GPT-4 as the LLM
    return search.invoke(query)
    


@tool
def bm25_search_tool(namespace: str) -> str:
    """
    Perform a search using BM25.
    :param namespace: The namespace to search for. e.g. mistune.plugins.table.table_in_quote
    :return: The retrieved search results
    """
    with open(BM25_SEARCH_FILE, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f]
    
    for item in data:
        if item["namespace"] == namespace:
            return item["retrieved"]
    
    return "No results found."

# New code formatting tool
@tool
def format_code_tool(code: str) -> str:
    """
    Format code using black.
    :param code: The code to be formatted
    :return: The formatted code
    """
    try:
        return black.format_str(code, mode=black.FileMode())
    except black.NothingChanged:
        return code  # Return the original code if it is already formatted
    except Exception as e:
        return f"Error formatting code: {str(e)}"

# 测试
if __name__ == "__main__":
    start_time = time.time()
    
    # test
    namespace = "mistune.toc.add_toc_hook"
    print(bm25_search_tool.invoke(namespace))
    