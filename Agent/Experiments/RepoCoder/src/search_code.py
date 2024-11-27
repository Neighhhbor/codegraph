import os
import json
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util
from multiprocessing import Process, Queue


# 设置代理和环境变量
os.environ['CUDA_VISIBLE_DEVICES'] = "2,3"
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"


# 模型服务进程
def model_service(model_name, request_queue, response_queue):
    print("Initializing model...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = SentenceTransformer(model_name, trust_remote_code=True, device=device)
    print("Model loaded and ready for requests.")

    while True:
        request = request_queue.get()
        if request == "shutdown":
            print("Shutting down model service...")
            break

        if "encode" in request:
            texts = request["encode"]
            embeddings = model.encode(texts, convert_to_tensor=True).cpu().numpy()
            response_queue.put(embeddings)

        elif "query" in request:
            query_text = request["query"]
            contexts = request["contexts"]
            query_embedding = model.encode(query_text, convert_to_tensor=True)
            context_embeddings = model.encode(contexts, convert_to_tensor=True)
            scores = util.cos_sim(query_embedding, context_embeddings)[0].cpu().numpy()
            response_queue.put(scores)


# RepoSearcher 类
class RepoSearcher:
    def __init__(self, model_name, request_queue, response_queue):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.model_name = model_name

    def compute_embeddings(self, contexts, batch_size=64):
        embeddings = []
        for i in tqdm(range(0, len(contexts), batch_size), desc="Processing embeddings", unit="batch"):
            batch_contexts = contexts[i:i + batch_size]
            self.request_queue.put({"encode": batch_contexts})
            batch_embeddings = self.response_queue.get()
            embeddings.extend(batch_embeddings)
        return embeddings

    def embedding_search(self, query, contexts, top_k=5):
        self.request_queue.put({"query": query, "contexts": contexts})
        scores = self.response_queue.get()
        top_indices = scores.argsort()[::-1][:top_k]
        results = [{"context": contexts[i], "score": scores[i]} for i in top_indices]
        return results


def process_all_repos(windowed_dir, embedding_dir, searcher, batch_size=64):
    os.makedirs(embedding_dir, exist_ok=True)
    for file_name in os.listdir(windowed_dir):
        if file_name.endswith("_windows.json"):
            project_name = file_name.replace("_windows.json", "")
            windowed_file = os.path.join(windowed_dir, file_name)
            embedding_file = os.path.join(embedding_dir, f"{project_name}_embeddings.json")

            if os.path.exists(embedding_file):
                print(f"Embeddings for {project_name} already exist. Skipping...")
                continue

            print(f"Processing project: {project_name}")
            with open(windowed_file, 'r', encoding='utf-8') as f:
                windows = json.load(f)

            contexts = [window["context"] for window in windows]
            embeddings = searcher.compute_embeddings(contexts, batch_size=batch_size)

            output_data = [
                {
                    "embedding": embedding.tolist(),
                    "context": windows[i]["context"],
                    "metadata": windows[i]["metadata"]
                }
                for i, embedding in enumerate(embeddings)
            ]
            with open(embedding_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)

            print(f"Saved {len(embeddings)} embeddings to {embedding_file}")


def query_repo(repo_name, embedding_dir, searcher, query, top_k=5):
    embedding_file = os.path.join(embedding_dir, f"{repo_name}_embeddings.json")
    if not os.path.exists(embedding_file):
        print(f"Embeddings for {repo_name} not found.")
        return

    with open(embedding_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    contexts = [item["context"] for item in data]
    results = searcher.embedding_search(query, contexts, top_k=top_k)

    print("Top-K Search Results:")
    for result in results:
        print(f"Context: {result['context']}\nScore: {result['score']}\n")


if __name__ == "__main__":
    # 模型名称
    model_name = "dunzhang/stella_en_400M_v5"

    # 创建通信队列
    request_queue = Queue()
    response_queue = Queue()

    # 启动模型服务进程
    model_process = Process(target=model_service, args=(model_name, request_queue, response_queue))
    model_process.start()

    try:
        # 输入窗口化数据目录和嵌入保存目录
        windowed_dir = "Windowed_Projects"
        embedding_dir = "Embeddings"

        searcher = RepoSearcher(model_name, request_queue, response_queue)

        print("Choose an operation:")
        print("1. Process all repos (calculate embeddings)")
        print("2. Query a specific repo")

        choice = input("Enter your choice (1 or 2): ").strip()

        if choice == "1":
            process_all_repos(windowed_dir, embedding_dir, searcher)
        elif choice == "2":
            repo_name = input("Enter the repo name (without '_windows.json'): ").strip()
            query = input("Enter your query: ").strip()
            query_repo(repo_name, embedding_dir, searcher, query)
        else:
            print("Invalid choice.")

    finally:
        # 关闭模型服务
        request_queue.put("shutdown")
        model_process.join()
