import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging
import torch

# 设置可见的 GPU 设备
os.environ['CUDA_VISIBLE_DEVICES'] = '4,5,6,7'  # 限制使用的 GPU 设备

class SemanticAnalyzer:
    def __init__(self, model_path=None):
        # 初始化Sentence Transformer模型
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 使用CUDA设备
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model_cache_dir = "/home/shixianjie/models"
        
        # 如果未指定模型路径，默认使用 "sentence-transformers/all-MiniLM-L6-v2"
        if model_path is None:
            model_path = "sentence-transformers/all-MiniLM-L6-v2"
        
        # 加载模型
        self.model = SentenceTransformer(model_path, cache_folder=model_cache_dir, device=self.device)
        self.logger.info(f"Model loaded from {model_path} on device {self.device}")

    def embed_code(self, code_snippet):
        """
        使用 embedding 模型对代码片段进行嵌入，返回嵌入向量。
        Args:
            code_snippet (str): 需要嵌入的代码字符串。
        Returns:
            numpy.ndarray: 代码的嵌入向量。
        """
        embedding = self.model.encode([code_snippet])
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
        similarity = cosine_similarity(embedding1, embedding2)[0][0]
        return similarity

    def find_similar_nodes(self, code_graph, threshold=0.7):
        """
        遍历代码图中的所有类和函数节点，计算它们之间的相似性，返回相似的节点对。
        Args:
            code_graph (CodeGraph): 包含代码结构的图。
            threshold (float): 相似度阈值，超过该值的节点会被视为相似。
        Returns:
            List[Tuple]: 相似节点对列表。
        """
        # 提取所有类和函数节点
        nodes = [(n, d) for n, d in code_graph.get_graph().nodes(data=True) if d['type'] in ['class', 'function']]
        embeddings = {}

        # 为每个节点计算 embedding
        for node, data in nodes:
            code = data.get('code', '')
            embeddings[node] = self.embed_code(code)

        # 计算两两节点的相似度，并筛选超过阈值的节点对
        similar_pairs = []
        for i, (node1, emb1) in enumerate(embeddings.items()):
            for j, (node2, emb2) in enumerate(embeddings.items()):
                if i >= j:
                    continue
                similarity = self.calculate_similarity(emb1, emb2)
                if similarity >= threshold:
                    self.logger.info(f"Similarity between {node1} and {node2}: {similarity}")
                    similar_pairs.append((node1, node2))

        return similar_pairs
