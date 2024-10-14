import torch
from sentence_transformers import SentenceTransformer
from multiprocessing import Process, Queue, Event
import time
import os
import socket
import numpy as np

# 设置 HuggingFace 镜像站点和代理
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

MODEL_SERVER_PORT = 5000  # 选择一个空闲端口

def model_server(ready_event):
    # 设置可见的 CUDA 设备为 2 和 3
    os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 加载模型
    model = SentenceTransformer("dunzhang/stella_en_400M_v5", trust_remote_code=True, device=device)
    print("模型已加载,服务就绪")
    ready_event.set()  # 通知主进程模型已加载完成

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', MODEL_SERVER_PORT))
        s.listen()
        ready_event.set()  # 通知主进程模型已加载完成
        
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(1024).decode()
                if data == 'status':
                    conn.sendall(b'running')
                elif data.startswith("embed:"):
                    text = data[6:]  # 去掉 "embed:" 前缀
                    result = model.encode(text)
                    conn.sendall(result.astype(np.float32).tobytes())
                elif data == "STOP":
                    break

    print("模型服务已停止")

# 全局变量来跟踪服务进程
model_process = None

def start_model_server():
    global model_process
    if model_process is None or not model_process.is_alive():
        ready_event = Event()
        model_process = Process(target=model_server, args=(ready_event,))
        model_process.start()
        ready_event.wait()  # 等待模型加载完成
        print("模型服务进程已启动并就绪")
    else:
        print("模型服务已经在运行")

def stop_model_server():
    global model_process
    if model_process and model_process.is_alive():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', MODEL_SERVER_PORT))
            s.sendall(b"STOP")
        model_process.join()
        print("模型服务已停止")
    else:
        print("模型服务未运行")

if __name__ == "__main__":
    start_model_server()
    print("模型服务正在后台运行。要停止服务，请按 Ctrl+C。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在停止模型服务...")
    finally:
        stop_model_server()
