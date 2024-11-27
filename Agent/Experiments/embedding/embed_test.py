import os
import json
import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import torch

# 配置设备和代理
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('embedding_process.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 路径和常量定义
TEST_DATA_PATH = '/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_merged.jsonl'
OUTPUT_EMBEDDINGS_FILE = "./input_code_embeddings.json"

# 初始化模型
logger.info("Loading model...")
model = SentenceTransformer("dunzhang/stella_en_400M_v5", trust_remote_code=True, device=device)
logger.info("Model loaded successfully")

# 加载测试数据
def load_test_data(test_data_path):
    with open(test_data_path, 'r') as f:
        return [json.loads(line) for line in tqdm(f, desc="加载测试数据")]

# 为每条测试数据生成并保存 input_code 嵌入
def generate_and_save_input_code_embeddings(test_data, output_file):
    embeddings_data = []

    # 处理每条测试数据
    for item in tqdm(test_data, desc="生成 input_code 嵌入"):
        namespace = item['namespace']
        input_code = item['input_code']
        
        try:
            # 计算 input_code 的嵌入向量
            embedding = model.encode(input_code).astype(np.float32)
            embeddings_data.append({
                'namespace': namespace,
                'embedding': embedding.tolist()  # 转换为列表以便 JSON 存储
            })
        except Exception as e:
            logger.error(f"Error processing {namespace}: {str(e)}")

    # 保存所有嵌入到本地 JSON 文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Input code embeddings saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving embeddings: {str(e)}")

# 主流程
def main():
    # 加载测试数据
    test_data = load_test_data(TEST_DATA_PATH)
    
    # 生成并保存 input_code 嵌入
    generate_and_save_input_code_embeddings(test_data, OUTPUT_EMBEDDINGS_FILE)

if __name__ == "__main__":
    main()
