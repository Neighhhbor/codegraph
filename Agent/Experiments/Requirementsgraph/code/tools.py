import os
import json
from typing import List, Dict, Any
from langchain.tools import tool
from tqdm import tqdm  # Import tqdm library for progress bar
import os
from langchain_community.tools import DuckDuckGoSearchRun
import black


# 设置 HuggingFace 镜像站点
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

MATA_DATAFILE = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/promptelements/LM_prompt_elements_merged.jsonl"
dependency_datafile = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/Requirementsgraph/code/filtered.jsonl"
repopath = "/home/shixianjie/codegraph/codegraph/Agent/repocode"
merged_data_file = "/home/shixianjie/codegraph/codegraph/Agent/Experiments/Requirementsgraph/code/merged_data.jsonl"

# Assume preloaded namespace to project path mapping
namespace_map = {}

merged_data = [json.loads(line) for line in open(merged_data_file, 'r', encoding='utf-8')]

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
    
    
# Tool: Search for related code based on the given namespace
@tool
def get_relative_code(namespace: str) -> Dict[str, Any]:
    """
    Search for related code based on the given namespace and its dependency information.

    Parameters
    ----------
    namespace : str
        The namespace for which related code is to be found.

    Returns
    -------
    dict
        A dictionary categorizing related code based on the types of dependencies:
        - "child_requirement"
        - "context_requirement"
        - "similarity_requirement"

    Notes
    -----
    This function:
    1. Loads the relevant code files (functions, methods, and classes) for the associated project.
    2. Searches for matching code entries based on dependency types: child, context, and similarity requirements.
    3. Returns a dictionary with categorized results containing the matching code, namespace, and path information.
    """
    # Step 1: Get the project path and dependencies for the given namespace
    data = {}
    for item in merged_data:
        if item["namespace"] == namespace:
            data = item
            break
    # Extract dependency and project path details
    dependency = data.get("dependency", {})
    reponame = data["project_path"].split("/")[-1]
    
    # Step 2: Define paths to the corresponding repo's JSONL files (functions, methods, classes)
    functions_jsonl = os.path.join(repopath, f"{reponame}_functions.json")
    methods_jsonl = os.path.join(repopath, f"{reponame}_methods.json")
    classes_jsonl = os.path.join(repopath, f"{reponame}_classes.json")
    
    # Load the code search space from these files, showing progress bars for file processing
    search_space = []
    files = [functions_jsonl, methods_jsonl, classes_jsonl]
    
    # Read files with a progress bar for each
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            search_space.extend([json.loads(line) for line in f])
    
    # Step 3: Retrieve the list of namespaces from the dependency data
    child_requirements = dependency.get("child_requirement", [])
    context_requirements = dependency.get("context_requirement", [])
    similarity_requirements = dependency.get("similarity_requirement", [])

    # Initialize the result dictionary to store the categorized code
    result = {
        "child_requirement": {
            "codes": []
        },
        "context_requirement": {
            "codes": []
        },
        "similarity_requirement": {
            "codes": []
        }
    }

    # Helper function: Search for matching code entries and fill the result dictionary
    def search_and_fill(namespace_list: List[str], category: str):
        nonlocal result
        for dep_namespace in namespace_list :
            # Find matching code for the given namespace
            matched_codes = [{"namespace": item.get("name", ""), "code": item.get("code", ""), "path": item.get("path", "")} 
                             for item in search_space 
                             if item.get("name") == dep_namespace]
            result[category]["codes"].extend(matched_codes)
    
    # Step 4: Search and fill for each dependency type (child, context, similarity)
    search_and_fill(child_requirements, "child_requirement")
    search_and_fill(context_requirements, "context_requirement")
    search_and_fill(similarity_requirements, "similarity_requirement")
    
    # Return the final result with categorized code
    return result


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
    
    
# Test
if __name__ == "__main__":
    # Example test data
    namespace = "mrjob.parse.is_s3_uri"
    dependency = {
        "child_requirement": ["mrjob.mrjob.parse.parse_s3_uri"],
        "context_requirement": ["mrjob.mrjob.fs.hadoop.HadoopFilesystem.can_handle_path"],
        "similarity_requirement": ["mrjob.mrjob.fs.gcs.is_gcs_uri", "mrjob.mrjob.fs.s3.S3Filesystem.can_handle_path"]
    }
    
    # Find related code
    related_code = get_relative_code(namespace)
    
    # Print the results
    print(json.dumps(related_code, indent=4, ensure_ascii=False))
