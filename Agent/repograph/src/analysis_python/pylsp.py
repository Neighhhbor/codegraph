import socket
import json
import os
import time
import networkx as nx
import logging
import concurrent.futures
import random
import re
import threading
import queue
from tqdm import tqdm
import sys
import argparse
import subprocess
import select
import asyncio
import multiprocessing


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def start_pylsp(port):
    """启动 pylsp 进程，并为其指定端口"""
    cmd = ['pylsp', '--tcp', '--host', '127.0.0.1', '--port', str(port)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.info(f"Started pylsp process on port {port}")
    return process

LSP_HOST = 'localhost'

opened_files = set()
request_id = 1
pending_requests = {}
response_queue = queue.Queue()
initialized = threading.Event()
pending_requests_lock = threading.Lock()

def send_request(sock, message):
    global request_id
    message["id"] = request_id
    with pending_requests_lock:
        pending_requests[request_id] = message
    request_id += 1

    message_str = json.dumps(message)
    content_length = len(message_str)
    header = f"Content-Length: {content_length}\r\n\r\n"
    full_message = header + message_str

    logging.debug(f"Sending Request (ID: {message['id']}):\n{full_message[:100]}...")

    try:
        sock.sendall(full_message.encode('utf-8'))
    except socket.error as e:
        logging.error(f"Socket error while sending request ID {message['id']}: {e}")
        with pending_requests_lock:
            del pending_requests[message["id"]]
        return False
    return True

def read_exact(sock, nbytes):
    data = b''
    while len(data) < nbytes:
        more = sock.recv(nbytes - len(data))
        if not more:
            raise EOFError(f'Expected {nbytes} bytes but only received {len(data)} bytes before the connection closed.')
        data += more
    return data

def receive_response(sock, reponame, stop_event=None):
    """接收 LSP 响应，如果超时或者连接失败，进行重试或跳过。"""
    sock.settimeout(2.0)  # 设置套接字超时
    while True:
        try:
            # 使用 select 处理非阻塞
            rlist, _, _ = select.select([sock], [], [], 0.1)
            if rlist:
                header = ""
                while "\r\n\r\n" not in header:
                    data = sock.recv(1)
                    if not data:
                        raise EOFError(f"Connection closed during header reading.")
                    header += data.decode('utf-8')

                match = re.search(r"Content-Length: (\d+)", header)
                if not match:
                    logging.error(f"Malformed header: {header}")
                    continue

                content_length = int(match.group(1))
                content = read_exact(sock, content_length).decode('utf-8')

                try:
                    message = json.loads(content)
                    logging.debug(f"{reponame} Received Message:\n{json.dumps(message, indent=2)}")
                    response_queue.put(message)
                except json.JSONDecodeError as e:
                    logging.error(f"JSON Decode Error: {content} - {e}")
                    continue  # 如果解析错误，继续等待下一条消息
            else:
                time.sleep(2)

        except (socket.error, EOFError, ConnectionError) as e:
            logging.info(f"{reponame} connection closed or error: {e}")
            if stop_event:
                stop_event.set()  # 设置停止事件，通知主进程结束
            return

def send_request_and_wait(sock, message, timeout=5, retries=3):
    """发送请求并等待响应，如果超时达到最大重试次数则返回 None"""
    send_request(sock, message)

    attempts = 0
    while attempts < retries:
        try:
            response = response_queue.get(timeout=timeout)
            logging.debug(f"Processing response: {json.dumps(response, indent=2)}")

            if "id" in response and response["id"] == message["id"]:
                logging.debug(f"Received response for request ID {message['id']}")
                with pending_requests_lock:
                    if message["id"] in pending_requests:
                        del pending_requests[message["id"]]
                return response
            else:
                response_queue.put(response)

        except queue.Empty:
            logging.warning(f"Timeout waiting for response to request ID {message['id']}. Retrying...")
            attempts += 1

    logging.info(f"Request ID {message['id']} timed out after {retries} attempts. Returning None.")
    return None

def initialize(sock, root_uri, initialized_event):
    message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {},
            "workspaceFolders": [{"uri": root_uri, "name": "Workspace"}]
        }
    }
    response = send_request_and_wait(sock, message, timeout=10, retries=3)
    if response and "result" in response:
        logging.info("PythonLanguage Server initialized successfully.")
        send_initialized_notification(sock)
        initialized_event.set()  # 设置当前 LSP 实例的初始化完成标志
    else:
        logging.error("Failed to initialize Python Language Server.")

def send_initialized_notification(sock):
    message = {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {}
    }
    send_request(sock, message)

def did_open_file(sock, file_uri, content):
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {
                "uri": file_uri,
                "languageId": "Python",
                "version": 1,
                "text": content
            }
        }
    }
    send_request(sock, message)

def request_definition(sock, file_uri, position):
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/definition",
        "params": {
            "textDocument": {"uri": file_uri},
            "position": position
        }
    }
    response = send_request_and_wait(sock, message, timeout=5, retries=3)
    logging.debug(f"Definition request response: {response}")
    if response and "result" in response:
        return response["result"]
    return None

def process_ast_nodes(socks, graph, stop_event, nodes_per_process=50000):
    total_nodes = len(graph.nodes)
    batch_size = 500  # 每批处理的节点数

    # 缓存已打开的文件，避免多次 didOpen 请求
    opened_files = set()

    # 处理 AST 节点
    def process_node(node_id, node_data, pbar):
        """处理每个节点的定义请求"""
        if stop_event.is_set():
            logging.debug("Stopping AST node processing due to timeout.")
            return

        if node_data["type"] in ['identifier'] and node_data.get("field_name") in ['function', 'attribute']:
            file_id = node_data["file_id"]
            file_path = graph.nodes[file_id]["path"]
            file_uri = f"file://{file_path}"

            position = {
                "line": node_data["sp"][0],
                "character": node_data["sp"][1]
            }

            # 缓存文件，减少 didOpen 请求的频繁发送
            if file_uri not in opened_files:
                with open(file_path, 'r') as f:
                    content = f.read()
                # 向所有LSP发送didOpen请求
                for sock in socks:
                    did_open_file(sock, file_uri, content)
                opened_files.add(file_uri)
                time.sleep(0.1)

            # 随机选择一个LSP来处理当前请求
            sock = random.choice(socks)  # 随机选择一个 LSP
            result = request_definition(sock, file_uri, position)

            if result is not None:
                node_data["definition"] = result
            else:
                logging.info(f"Skipping node {node_id} due to repeated timeouts.")

        pbar.update(1)  # 更新进度条

    # 使用进程池并行处理 AST 节点
    with multiprocessing.Pool(processes=len(socks)) as pool:
        results = []
        with tqdm(total=total_nodes, desc="Processing AST Nodes", unit="node", ncols=100) as pbar:
            # 每5000个节点重启LSP进程
            for i, (node_id, node_data) in enumerate(graph.nodes(data=True)):
                results.append(pool.apply_async(process_node, (node_id, node_data, pbar)))

                if i % nodes_per_process == 0:
                    pool.terminate()
                    pool.join()  # 等待当前的进程池结束
                    logging.info(f"Restarting LSP processes after processing {i} nodes.")
                    pool = multiprocessing.Pool(processes=len(socks))  # 重新启动进程池

        # 等待所有任务完成
        for result in results:
            result.get()



def connect_with_exponential_backoff(sock, host, port, max_retries=5, initial_delay=2, max_delay=30):
    attempt = 0
    delay = initial_delay
    
    while attempt < max_retries:
        try:
            sock.connect((host, port))
            logging.info(f"Successfully connected to LSP server at {host}:{port}")
            return True
        except ConnectionRefusedError:
            logging.error(f"Connection failed on attempt {attempt + 1}. Retrying in {delay} seconds...")
            attempt += 1
            time.sleep(delay)
            delay = min(delay * 2, max_delay)

    logging.error(f"Failed to connect to LSP server at {host}:{port} after {max_retries} attempts.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    parser.add_argument('--ports', type=int, nargs='+', required=True, help="Ports for the multiple pylsp servers.")
    
    args = parser.parse_args()

    pylsp_processes = []
    socks = []
    initialized_events = []  # 用于存储每个 LSP 实例的初始化事件

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    
    output_path = os.path.join(results_dir, 'definitiongraph.json')
    if os.path.exists(output_path):
        logging.info(f"Output file already exists: {output_path}. Skipping processing.")
        return

     # 启动多个 pylsp 进程
    for port in args.ports:
        pylsp_process = start_pylsp(port)
        pylsp_processes.append(pylsp_process)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socks.append(sock)
        initialized_events.append(threading.Event())  # 为每个 LSP 创建一个独立的事件


    root_uri = f"file://{repo_path}"
    graph_path = os.path.join(results_dir, 'repoparser.json')
    try:
        with open(graph_path, 'r') as f:
            graph = nx.node_link_graph(json.load(f))
    except FileNotFoundError:
        logging.debug(f"{repo_path} Graph file not found: {graph_path}")
        return

    stop_event = threading.Event()

    # 连接到所有 LSP 服务器并初始化
    for i, sock in enumerate(socks):
        lspport = args.ports[i]
        logging.info(f"Connecting to LSP server on port {lspport}")
        if not connect_with_exponential_backoff(sock, LSP_HOST, lspport):
            logging.error(f"Cannot connect to LSP server on port {lspport}.")
            return

        sock.settimeout(20.0)
        response_thread = threading.Thread(target=receive_response, args=(sock, repo_path, stop_event))
        response_thread.daemon = True
        response_thread.start()

        initialize(sock, root_uri, initialized_events[i])

    # 等待所有 LSP 完成初始化
    for event in initialized_events:
        event.wait()

    if stop_event.is_set():
        logging.error("Stopping due to response timeouts.")
        for pylsp_process in pylsp_processes:
            pylsp_process.terminate()
            pylsp_process.wait()
        return

    # 处理 AST 节点
    process_ast_nodes(socks, graph, stop_event)
    stop_event.set()


    os.makedirs(results_dir, exist_ok=True)
    output_path = os.path.join(results_dir, 'definitiongraph.json')
    with open(output_path, 'w') as f:
        json.dump(nx.node_link_data(graph), f, indent=4)
        
    try:
        os.remove(graph_path)
    except FileNotFoundError:
        logging.debug(f"Graph file not found: {graph_path}")
        
    for pylsp_process in pylsp_processes:
        pylsp_process.terminate()
        pylsp_process.wait()


    
if __name__ == "__main__":
    main()
