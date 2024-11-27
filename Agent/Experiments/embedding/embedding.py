import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging
import torch

# Set device
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Set proxy and Hugging Face mirror settings
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('embedding_process.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize the model
logger.info("Loading model...")
model = SentenceTransformer("dunzhang/stella_en_400M_v5", trust_remote_code=True, device=device)
logger.info("Model loaded successfully")

def compute_and_save_embeddings_for_all_functions(repocode_dir, output_dir):
    """
    Compute and save embeddings for all functions in the repocode directory.
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all relevant function files
    json_files = [f for f in os.listdir(repocode_dir) if f.endswith(".json") and "functions" in f]
    logger.info(f"Found {len(json_files)} function files to process")
    
    # Iterate over each file and show progress for each
    for file_name in tqdm(json_files, desc="Processing files"):
        function_file_path = os.path.join(repocode_dir, file_name)
        output_file_path = os.path.join(output_dir, f"embeddings_{file_name}")
        logger.info(f"Starting file: {file_name}")
        compute_and_save_embeddings(function_file_path, output_file_path)
        logger.info(f"Completed file: {file_name}")

def compute_and_save_embeddings(function_file, embedding_file):
    """
    Compute and save embeddings for functions in a given JSONL file.
    """
    embeddings = []
    function_names = []
    
    # Read the function data file (JSONL format)
    with open(function_file, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f]
        logger.info(f"Read {len(data)} functions from file {function_file}")
        
        # Show a progress bar for processing each function in the file
        with tqdm(total=len(data), desc=f"Processing {os.path.basename(function_file)}", leave=False) as pbar:
            for function_data in data:
                code = function_data.get('code', '')
                try:
                    embedding = model.encode(code).astype(np.float32)
                    embeddings.append(embedding.tolist())  # Store as list for JSON serialization
                    function_names.append(function_data['name'])
                except Exception as e:
                    logger.error(f"Error processing function {function_data['name']} in {function_file}: {str(e)}")
                pbar.update(1)  # Update the progress bar for each function processed
    
    # Save the embeddings and function names to the output file
    try:
        with open(embedding_file, 'w', encoding='utf-8') as f:
            json.dump({'functions': function_names, 'embeddings': embeddings}, f, ensure_ascii=False, indent=4)
        logger.info(f"Saved embeddings to {embedding_file}")
    except Exception as e:
        logger.error(f"Error saving embeddings for {function_file}: {str(e)}")

# Example usage
repocode_dir = '/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/EmbeddingRAG/repocode'  # Directory containing the repocode files
output_dir = './embeddings'  # Directory to save embeddings

# Compute and save embeddings for all files
compute_and_save_embeddings_for_all_functions(repocode_dir, output_dir)
