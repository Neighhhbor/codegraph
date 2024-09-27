import os
from semantic_analyzer import SemanticAnalyzer
from code_graph import CodeGraph
import networkx as nx
import logging

# 设置日志记录
logging.basicConfig(level=logging.INFO, format=' %(name)s - %(levelname)s - %(message)s')

# 手动生成一个自然语言描述
def generate_nl_description():
    """
    模拟生成一个自然语言描述，用于描述给定代码的功能。
    """
    nl_query = "This function registers a new feature with a namespace variable and ensures it is unique."
    return nl_query

def main():
    # Step 1: 初始化 SemanticAnalyzer
    semantic_analyzer = SemanticAnalyzer()

    # Step 2: 模拟从已生成的 CodeGraph 中提取的代码片段
    code_snippet = """
    This function registers a new feature with a namespace variable and ensures it is unique.
    def register_feature(self, var):
        if var in self._features or var in self.STATIC_FEATURES:
            raise ValueError("feature already claimed: {!r}".format(var))
        self._features.add(var)
        self.on_info_changed()
    """

    # Step 3: 为代码片段生成嵌入
    code_embedding = semantic_analyzer.embed_code(code_snippet)

    # Step 4: 生成自然语言描述
    nl_query = generate_nl_description()

    # Step 5: 为自然语言描述生成嵌入
    nl_embedding = semantic_analyzer.embed_natural_language(nl_query)

    # Step 6: 计算自然语言描述和代码片段之间的相似度
    similarity = semantic_analyzer.calculate_similarity(nl_embedding, code_embedding)
    
    print(f"Similarity between NL and code: {similarity}")

if __name__ == "__main__":
    main()
