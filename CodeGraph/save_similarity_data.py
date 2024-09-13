import csv
import json
import os

def save_similarity_to_csv(similar_pairs, similarities, filename="similarity_data.csv"):
    """
    将相似性数据保存为 CSV 文件
    """
    # 确保 ../data_process 目录存在
    output_dir = "../data_process/similarity"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)

    with open(filepath, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Node1", "Node2", "Similarity"])  # 写入表头
        for (node1, node2), similarity in zip(similar_pairs, similarities):
            writer.writerow([node1, node2, float(similarity)])  # 确保 similarity 是 float 类型
    print(f"Similarity data saved to {filepath}")


def save_similarity_to_json(similar_pairs, similarities, filename="similarity_data.json"):
    """
    将相似性数据保存为 JSON 文件
    """
    # 确保 ../data_process 目录存在
    output_dir = "../data_process/similarity"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)

    similarity_data = []
    for (node1, node2), similarity in zip(similar_pairs, similarities):
        similarity_data.append({
            "node1": node1,
            "node2": node2,
            "similarity": float(similarity)  # 将 similarity 转换为标准 float 类型
        })
    
    with open(filepath, mode='w') as file:
        json.dump(similarity_data, file, indent=4)
    print(f"Similarity data saved to {filepath}")
