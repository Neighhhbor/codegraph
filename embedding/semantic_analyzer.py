import os
import numpy as np
import torch
from sklearn.metrics.pairwise import cosine_similarity
import logging
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize  # 导入归一化方法

# 设置可见的 GPU 设备
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
# 1. Specify preffered dimensions
DIMENSIONS = 512

# 2. load model
class SemanticAnalyzer:
    def __init__(self, model_path="/home/sxj/models"):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # 确保使用 GPU (如果可用)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=model_path, device=self.device)
        # self.model = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1", cache_folder=model_path, device=self.device,truncate_dim=DIMENSIONS)
        self.model = SentenceTransformer("dunzhang/stella_en_400M_v5", trust_remote_code=True, cache_folder=model_path, device=self.device)
        # self.model = SentenceTransformer("dunzhang/stella_en_1.5B_v5", trust_remote_code=True,cache_folder=model_path, device=self.device)
        
        # 将模型移到指定设备
        self.model = self.model.to(self.device)
        
        self.logger.info(f"Model loaded on device {self.device}")

    def embed_code(self, code_snippet):
        """
        使用 embedding 模型对代码片段进行嵌入，返回归一化后的嵌入向量。
        Args:
            code_snippet (str): 需要嵌入的代码字符串。
        Returns:
            numpy.ndarray: 代码的归一化嵌入向量。
        """
        # 将输入转换为 float16 (如果在 GPU 上运行)
        if self.device.type == 'cuda':
            with torch.cuda.amp.autocast():
                embedding = self.model.encode(code_snippet)
        else:
            embedding = self.model.encode(code_snippet)
        
        # 对嵌入向量进行 L2 归一化
        normalized_embedding = normalize(embedding.reshape(1, -1), norm='l2')[0]
        
        return normalized_embedding

    def calculate_similarity(self, embedding1, embedding2):
        """
        计算两个归一化后的嵌入向量之间的余弦相似度。
        Args:
            embedding1 (numpy.ndarray): 第一个嵌入向量。
            embedding2 (numpy.ndarray): 第二个嵌入向量。
        Returns:
            float: 两个嵌入向量的余弦相似度。
        """
        embedding1 = embedding1.reshape(1, -1)
        embedding2 = embedding2.reshape(1, -1)
        similarity = cosine_similarity(embedding1, embedding2)[0][0]
        return similarity

    def find_similar_nodes(self, code_graph, threshold=0.90):
        """
        遍历代码图中的所有类和函数节点，计算它们之间的相似性，返回相似的节点对和对应的相似度。
        Args:
            code_graph (CodeGraph): 包含代码结构的图。
            threshold (float): 相似度阈值，超过该值的节点会被视为相似。
        Returns:
            List[Tuple]: 相似节点对列表。
            List[float]: 对应的相似度列表。
        """
        nodes = [(n, d) for n, d in code_graph.get_graph().nodes(data=True) if d['type'] in ['module','class','function']]
        embeddings = {}

        # 为每个节点计算 embedding，并归一化
        for node, data in nodes:
            code = data.get('code', '')
            embeddings[node] = self.embed_code(code)

        # 计算两两节点的相似度，并筛选超过阈值的节点对
        similar_pairs = []
        similarities = []
        for i, (node1, emb1) in enumerate(embeddings.items()):
            for j, (node2, emb2) in enumerate(embeddings.items()):
                if i >= j:
                    continue
                similarity = self.calculate_similarity(emb1, emb2)
                if similarity >= threshold:
                    self.logger.info(f"Similarity between {node1} and {node2}: {similarity}")
                    similar_pairs.append((node1, node2))
                    similarities.append(similarity)

        return similar_pairs, similarities
