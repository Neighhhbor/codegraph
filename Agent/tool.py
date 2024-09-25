import os
from langchain.tools import tool
from typing import List, Dict, Any
from CodeGraph import code_graph
import networkx as nx


codegraph = nx.read_gml("/home/sxj/Desktop/Workspace/CodeQl/gptgraph/CodeGraph/results/code_graph.gml")
print(codegraph)
@tool
def find_anchors(node_label) ->  List[Dict[str, Any]]:
    """Use this to find anchors based on the provided node label."""
    
    anchors = []
    context_above = get_context_above(node_label)
    anchors.append({"context_above": context_above})

    context_below = get_context_below(node_label)
    anchors.append({"context_below": context_below})

    imported_modules = get_imported_modules(node_label)
    anchors.append({"imported_modules": imported_modules})

    involved_names = get_involved_names(node_label)
    anchors.append({"involved_names": involved_names})

    bm25_results = get_bm25_results(node_label)
    anchors.append({"bm25_results": bm25_results})

    return anchors

@tool
def get_related_node(node_label) -> Dict[str, Any]:
    """Use this to get related nodes based on the provided node label."""
    
    related_node = {}
    context_above = get_context_above(node_label)
    related_node["context_above"] = context_above

    context_below = get_context_below(node_label)
    related_node["context_below"] = context_below

    imported_modules = get_imported_modules(node_label)
    related_node["imported_modules"] = imported_modules

    involved_names = get_involved_names(node_label)
    related_node["involved_names"] = involved_names

    bm25_results = get_bm25_results(node_label)
    related_node["bm25_results"] = bm25_results

    return related_node

# 辅助函数的实现
def get_context_above(node_label):
    return "上文内容示例"

def get_context_below(node_label):
    return "下文内容示例"

def get_imported_modules(node_label):
    return ["module_a", "module_b"]

def get_involved_names(node_label):
    return ["ClassA", "function_x", "global_param"]

def get_bm25_results(node_label):
    return ["result1", "result2"]



