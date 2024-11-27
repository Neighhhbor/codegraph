import torch
from sentence_transformers import SentenceTransformer
from multiprocessing import Process, Event
import os
import socket
import numpy as np
import time
import logging

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 设置 HuggingFace 镜像站点和代理
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['http_proxy'] = "http://127.0.0.1:7890"
os.environ['https_proxy'] = "http://127.0.0.1:7890"
os.environ['all_proxy'] = "socks5://127.0.0.1:7890"

MODEL_SERVER_PORT = 5000  # 嵌入模型服务端口

def model_server(ready_event):
    # 设置 CUDA 设备
    os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 加载模型
    model = SentenceTransformer("dunzhang/stella_en_400M_v5", trust_remote_code=True, device=device)
    logging.info("模型已加载, 服务就绪")
    ready_event.set()  # 通知主进程模型已加载完成

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', MODEL_SERVER_PORT))
        s.listen()
        
        while True:
            conn, addr = s.accept()
            with conn:
                logging.info(f"Connection established with {addr}")
                request_data = receive_all(conn)  # 接收完整数据
                
                if request_data.startswith("embed:"):
                    text = request_data[6:]  # 去掉 "embed:" 前缀
                    logging.info(f"Received text for embedding: '{text[:50]}...' (length: {len(text)})")
                    try:
                        result = model.encode(text)
                        logging.info("Embedding computed successfully")
                        send_all(conn, result.astype(np.float32).tobytes())
                    except Exception as e:
                        logging.error(f"Error during embedding computation: {e}")
                        send_all(conn, b"ERROR: Embedding computation failed")
                elif request_data.strip() == "status":
                    logging.info("Received status request")
                    send_all(conn, b'running')
                elif request_data.strip() == "STOP":
                    logging.info("Received stop signal")
                    break
    logging.info("模型服务已停止")

def receive_all(conn, buffer_size=4096):
    """完整接收数据，直到检测到 <END> 标记"""
    data = []
    while True:
        part = conn.recv(buffer_size)
        if not part:
            break
        data.append(part)
        if b"<END>" in part:
            break
    full_data = b''.join(data).replace(b"<END>", b"").decode(errors='ignore')
    logging.info(f"Data received: '{full_data[:50]}...' (total length: {len(full_data)})")
    return full_data

def send_all(conn, data, end_marker=b"<END>"):
    """完整发送数据，确保所有数据发送出去"""
    data += end_marker
    total_sent = 0
    while total_sent < len(data):
        sent = conn.send(data[total_sent:])
        if sent == 0:
            raise RuntimeError("Socket connection broken")
        total_sent += sent
    logging.info(f"Data sent successfully (total length: {len(data)})")

# 启动和停止模型服务
model_process = None

def start_model_server():
    global model_process
    if model_process is None or not model_process.is_alive():
        ready_event = Event()
        model_process = Process(target=model_server, args=(ready_event,))
        model_process.start()
        ready_event.wait()  # 等待模型加载完成
        logging.info("模型服务进程已启动并就绪")
    else:
        logging.info("模型服务已经在运行")

def stop_model_server():
    global model_process
    if model_process and model_process.is_alive():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', MODEL_SERVER_PORT))
            send_all(s, b"STOP")
        model_process.join()
        logging.info("模型服务已停止")
    else:
        logging.info("模型服务未运行")

if __name__ == "__main__":
    start_model_server()
    logging.info("模型服务正在后台运行。要停止服务，请按 Ctrl+C。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("正在停止模型服务...")
    finally:
        stop_model_server()
