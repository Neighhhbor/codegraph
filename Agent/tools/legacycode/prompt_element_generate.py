import json
import os
import logging
import sys
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import networkx as nx
import mimetypes
from tqdm import tqdm

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global cache for function embeddings, namespace table, and graph data
function_embeddings_cache = {}  # Cache to store embeddings per project
namespace_table = set()  # Set to keep track of processed namespaces
graph_cache = {}  # Cache for loaded graph data
namespace_lock = Lock()  # Lock for synchronizing access to the namespace table
import_analyzer_lock = Lock()  # Lock for synchronizing access to ImportAnalyzer instances
output_file_lock = Lock()  # Lock for synchronizing access to output file writes

# Load import analyzer module
sys.path.append('/home/shixianjie/codegraph/codegraph/')
from Agent.tools.import_analyzer import ImportAnalyzer

# Embedding related functions
def get_embedding(text, max_retries=3):
    MODEL_SERVER_PORT = 5000  # Replace with actual model server port
    for attempt in range(max_retries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', MODEL_SERVER_PORT))
                s.sendall(f"embed:{text}".encode())

                response = s.recv(4096)  # Assuming the embedding won't exceed 4096 bytes
                logging.info('Received embedding response')
                return np.frombuffer(response, dtype=np.float32).tolist()
        except Exception as e:
            logging.error(f"Error getting embedding (attempt {attempt + 1}/{max_retries}): {e}")
            import time
            time.sleep(1)
    return None

# Import analysis related functions
def get_imported_code(project_root, element):
    if 'project_path' in element and 'completion_path' in element:
        project_path = os.path.join(project_root, "DevEval/Source_Code", element['project_path'])
        file_path = os.path.join(project_root, "DevEval/Source_Code", element['completion_path'])
        logging.info(f'Analyzing imports for file: {file_path} within project: {project_path}')

        # Check if the file is a Python source file before proceeding
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith("text") or not file_path.endswith(".py"):
            logging.error(f"File {file_path} is not a valid Python source file.")
            return ""

        try:
            with import_analyzer_lock:
                analyzer = ImportAnalyzer(file_path, project_path)
                import_results = analyzer.analyze()
            imported_code = [{"import_statement": result['import'], "code": result.get('code', '')} for result in import_results]
            return imported_code
        except Exception as e:
            logging.error(f"Error analyzing imports for {file_path}: {e}")
            return ""
    return ""

# Main function for adding context and similarity analysis
def add_context_imports(merged_file, project_root, output_file, limit=None, embeddings_dir=None, max_workers=32):
    # Load all function embeddings into cache if not already loaded
    global function_embeddings_cache
    if embeddings_dir:
        logging.info('Loading all function embeddings into cache per project')
        embedding_files = list(Path(embeddings_dir).rglob("*.npz"))
        logging.info(f'Found {len(embedding_files)} embedding files')
        for embedding_file in embedding_files:
            project_name = Path(embedding_file).stem.split('_embeddings')[0]
            if project_name not in function_embeddings_cache:
                function_embeddings_cache[project_name] = {}
            try:
                data = np.load(embedding_file, allow_pickle=True)
            except (Exception, ValueError, OSError) as e:
                logging.error(f'Error loading embedding file {embedding_file}: {e}')
                continue
            for key in data.files:
                if isinstance(data[key], np.ndarray):
                    function_embeddings_cache[project_name][key] = {
                        'embedding': data[key].astype(float),
                        'code': key  # Replace this with actual code if available or a link to fetch the code
                    }
        logging.info('Finished loading embeddings into cache per project')

    # Load merged elements and prepare to process each worker
    logging.info('Starting to add context imports to elements')
    with open(merged_file, 'r') as f:
        elements = []
        for line in f:
            try:
                element = json.loads(line)
                # Validate that the element contains required keys
                if 'namespace' in element and 'project_path' in element and 'completion_path' in element:
                    elements.append(element)
                else:
                    logging.warning(f"Skipping invalid element due to missing keys: {element}")
            except json.JSONDecodeError:
                logging.warning(f"Skipping invalid JSON line: {line.strip()}")

    if limit is not None:
        elements = elements[:limit]

    # Load already processed namespaces from the output file to avoid redundancy
    cache = {}
    if os.path.exists(output_file):
        with open(output_file, 'r') as out_f:
            for line in out_f:
                try:
                    existing_element = json.loads(line)
                    if 'namespace' in existing_element:
                        namespace = existing_element['namespace']
                        cache[namespace] = existing_element
                        namespace_table.add(namespace)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON from output file: {e}")

    # Distribute elements across workers to avoid duplicate work
    elements_to_process = [element for element in elements if element.get('namespace') not in namespace_table]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_element, element, project_root, embeddings_dir, output_file, cache) for element in elements_to_process
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error processing element: {e}")

# Process each element to add context and similarity information
def process_element(element, project_root, embeddings_dir, output_file, cache):
    namespace = element.get('namespace', None)
    if not namespace:
        logging.warning('Element does not contain a namespace')
        return None
    
    # Check if the namespace has already been processed
    with namespace_lock:
        if namespace in namespace_table:
            logging.info(f'Namespace {namespace} already processed, skipping.')
            return None
        # Mark namespace as processed
        namespace_table.add(namespace)
    
    # Add contexts_import using ImportAnalyzer
    logging.info(f'Adding contexts_import for namespace {namespace}')
    element['contexts_import'] = get_imported_code(project_root, element)
    # Find most similar function
    logging.info(f'Finding most similar function for namespace {namespace}')
    element['most_similar_function'] = find_most_similar_function(element, embeddings_dir, codegraph_dir="/home/shixianjie/codegraph/codegraph/data_process/graphs")
    
    # Update the cache and write to output file
    cache[namespace] = element
    with output_file_lock:
        with open(output_file, 'a') as out_f:
            json.dump(convert_to_serializable(element), out_f)
            out_f.write('\n')
    
    return element

# Find the most similar function using cached embeddings
def find_most_similar_function(element, embeddings_dir, codegraph_dir="/home/shixianjie/codegraph/codegraph/data_process/graphs"):
    if not embeddings_dir or 'input_code' not in element or 'project_path' not in element:
        return ""
        
    logging.info('Getting embedding for input code')
    project_name = element['project_path'].split('/')[-1]
    graph_file_path = os.path.join(codegraph_dir, f"{project_name}.json")

    # Load the graph from cache if available
    if project_name in graph_cache:
        logging.info(f'Loading graph for project {project_name} from cache')
        codegraph = graph_cache[project_name]
    else:
        logging.info(f'Loading graph file from {graph_file_path}')
        if not os.path.exists(graph_file_path):
            logging.error(f'Graph file not found: {graph_file_path}')
            return ""
        # Load the graph
        try:
            with open(graph_file_path, 'r') as graph_file:
                graph_data = json.load(graph_file)
            codegraph = nx.node_link_graph(graph_data)
            graph_cache[project_name] = codegraph
            logging.info(f'Graph file loaded successfully for project: {project_name}')
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f'Error loading graph file {graph_file_path}: {e}')
            return ""
    
    query_embedding = get_embedding(element['input_code'])
    logging.info('Finished getting embedding for input code')
    if query_embedding is None:
        return "Unable to obtain query function embedding."

    # Extract function embeddings from the project-specific graph
    project_function_embeddings = function_embeddings_cache.get(project_name, {})

    # Find the most similar function using cosine similarity
    best_similarity = -1
    best_node = None
    logging.info('Starting similarity calculations within the project scope')
    for node, value in tqdm(project_function_embeddings.items(), desc="Calculating similarities"):
        embedding = value['embedding']
        similarity = float(cosine_similarity([query_embedding], [embedding])[0][0])
        if similarity > best_similarity and not node.endswith(element['namespace']):
            best_similarity = similarity
            best_node = node

    logging.info(f'Calculated similarities for all functions within the project')

    if best_node:
        logging.info('Most similar function found successfully after filtering ground truth matches')
        # Extract the code from the graphs
        node_data = codegraph.nodes.get(best_node, {})
        node_code = node_data.get('code', '')
        return {
            "code": node_code,
            "node_label": best_node,
            "similarity": best_similarity
        }
    else:
        return "No similar function found."

# Utility function to convert objects to serializable format
def convert_to_serializable(obj):
    if isinstance(obj, np.float32):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(i) for i in obj]
    else:
        return obj

if __name__ == "__main__":
    merged_file_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_merged.jsonl"
    project_root_path = "/home/shixianjie/codegraph/codegraph/"
    output_file_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_with_contexts.jsonl"

    embeddings_directory = "/home/shixianjie/codegraph/codegraph/data_process/embeddings"
    add_context_imports(merged_file_path, project_root_path, output_file_path, limit=None, embeddings_dir=embeddings_directory, max_workers=96)
