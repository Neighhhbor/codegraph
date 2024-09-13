import os
import numpy as np
import torch
from sklearn.metrics.pairwise import cosine_similarity
import logging
from sentence_transformers import SentenceTransformer

# 设置可见的 GPU 设备
os.environ['CUDA_VISIBLE_DEVICES'] = '7'

class SemanticAnalyzer:
    def __init__(self, model_path="/home/shixianjie/models"):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  # 优先使用GPU
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=model_path, device=self.device)
        self.logger.info(f"Model loaded on device {self.device}")

    def embed_code(self, code_snippet):
        """
        使用 embedding 模型对代码片段进行嵌入，返回嵌入向量。
        Args:
            code_snippet (str): 需要嵌入的代码字符串。
        Returns:
            numpy.ndarray: 代码的嵌入向量。
        """
        embedding = self.model.encode(code_snippet)
        return embedding

    def calculate_similarity(self, embedding1, embedding2):
        """
        计算两个嵌入向量之间的余弦相似度。
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

    def find_similar_nodes(self, code_graph, threshold=0.85):
        """
        遍历代码图中的所有类和函数节点，计算它们之间的相似性，返回相似的节点对和对应的相似度。
        Args:
            code_graph (CodeGraph): 包含代码结构的图。
            threshold (float): 相似度阈值，超过该值的节点会被视为相似。
        Returns:
            List[Tuple]: 相似节点对列表。
            List[float]: 对应的相似度列表。
        """
        nodes = [(n, d) for n, d in code_graph.get_graph().nodes(data=True) if d['type'] in ['function']]
        embeddings = {}

        # 为每个节点计算 embedding
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
