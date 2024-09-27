import os
import json
import logging
import sys
sys.path.append('/home/sxj/Desktop/Workspace/CodeQl/gptgraph')  # 确保这条路径是包含 CodeGraph 文件夹的路径
from CodeGraph.parsers import Node, ContainsParser

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def write_json(data, output_path, filename):
    """Write data to a JSON file, one item per line."""
    path = os.path.join(output_path, filename)
    try:
        with open(path, 'w') as file:
            for item in data:
                json.dump(item, file)
                file.write('\n')
    except Exception as e:
        logging.error(f"Failed to write JSON to {path}: {e}")

def analyze_repo(repo_path, repo_name, output_path):
    """Analyze Python files within a repository and extract classes, functions, and methods."""
    logging.debug(f"Starting analysis for repository: {repo_name}")
    try:
        parser = ContainsParser(repo_path, repo_name)
        parser.parse()
    except Exception as e:
        logging.error(f"Error parsing repository {repo_name} at {repo_path}: {e}")
        return
    
    functions = []
    classes = []
    methods = []

    # Traverse all nodes to extract functions, classes, and methods
    # print(len(parser.nodes))
    for node_fullname, node in parser.nodes.items():
        # print(node_fullname, node.node_type)
        if node.node_type == 'function':
            functions.append({'name': node.fullname, 'code': node.code})
            logging.debug(f"Extracted function: {node.fullname}")
        elif node.node_type == 'class':
            classes.append({'name': node.fullname, 'code': node.code})
            logging.debug(f"Extracted class: {node.fullname}")
            for child in node.children:
                if child.node_type == 'function':
                    methods.append({'name': child.fullname, 'code': child.code})
                    logging.debug(f"Extracted method: {child.fullname}")

    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Write the extracted data to JSON files
    write_json(functions, output_path, f'{repo_name}_functions.json')
    write_json(classes, output_path, f'{repo_name}_classes.json')
    write_json(methods, output_path, f'{repo_name}_methods.json')

def main(input_path, output_path):
    """Main function to walk through the directory structure and analyze each repository."""
    for category in os.listdir(input_path):
        category_path = os.path.join(input_path, category)
        if os.path.isdir(category_path):
            for repo in os.listdir(category_path):
                repo_path = os.path.join(category_path, repo)
                if os.path.isdir(repo_path):
                    logging.info(f"Analyzing {repo} in {category}...")
                    analyze_repo(repo_path, repo, output_path)

if __name__ == '__main__':
    source_code_dir = '/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/Source_Code'
    output_dir = './repocode'
    main(source_code_dir, output_dir)
