import socket
import json
import os
import time
import networkx as nx
import logging
import re
import threading
import queue
from tqdm import tqdm
import sys
import argparse
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

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


def receive_response(sock):
    sock.settimeout(30.0)
    while True:
        try:
            header = ""
            while "\r\n\r\n" not in header:
                header += sock.recv(1).decode('utf-8')

            match = re.search(r"Content-Length: (\d+)", header)
            if not match:
                logging.error(f"Malformed header: {header}")
                continue

            content_length = int(match.group(1))
            content = read_exact(sock, content_length).decode('utf-8')

            try:
                message = json.loads(content)
                logging.debug(f"Received Message:\n{json.dumps(message, indent=2)}")
                response_queue.put(message)
            except json.JSONDecodeError as e:
                logging.error(f"JSON Decode Error: {content} - {e}")
        except socket.timeout as e:
            logging.warning(f"Socket timeout while receiving response: {e}")
            continue  # 发生 timeout 后继续监听
        except (socket.error, ConnectionError) as e:
            logging.info(f"connection closed")
            break  # 发生 socket 错误或连接关闭时退出



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
                return response  # 返回成功的响应
            else:
                response_queue.put(response)  # 将不相关的响应重新放回队列

        except queue.Empty:
            logging.warning(f"Timeout waiting for response to request ID {message['id']}. Retrying...")
            attempts += 1

    logging.error(f"Failed to get a response for request ID {message['id']} after {retries} attempts.")
    return None  # 超时或达到最大重试次数后返回 None



def initialize(sock, root_uri):
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
    response = send_request_and_wait(sock, message, timeout=15, retries=5)
    if response and "result" in response:
        logging.info("PythonLanguage Server initialized successfully.")
        send_initialized_notification(sock)
        initialized.set()
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
    """Send a definition request and wait for the response."""
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


    
def process_ast_nodes(sock, graph):
    total_nodes = len(graph.nodes)
    batch_size = 500  # 每批处理的节点数量

    with tqdm(total=total_nodes, desc="Processing AST Nodes", unit="node") as pbar:
        for i, (node_id, node_data) in enumerate(graph.nodes(data=True)):
            if node_data["type"] in ['identifier'] and node_data.get("field_name") in ['function', 'attribute']:
                file_id = node_data["file_id"]
                file_path = graph.nodes[file_id]["path"]
                file_uri = f"file://{file_path}"

                position = {
                    "line": node_data["sp"][0],
                    "character": node_data["sp"][1]
                }

                if file_uri not in opened_files:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    did_open_file(sock, file_uri, content)
                    opened_files.add(file_uri)

                # 请求符号定义，并检查是否超时返回 None
                result = request_definition(sock, file_uri, position)
                if result is not None:
                    node_data["definition"] = result  # 只有在有响应时才更新定义
                else:
                    logging.info(f"Skipping node {node_id} due to repeated timeouts.")

            if i % batch_size == 0:
                time.sleep(0.1)  # 轻微的暂停，防止服务器过载

            pbar.update(1)


def connect_with_exponential_backoff(sock, host, port, max_retries=5, initial_delay=2, max_delay=30):
    """
    尝试连接到 LSP 服务器，并实现指数回退机制。
    
    :param sock: 已创建的 socket 对象
    :param host: LSP 服务器主机
    :param port: LSP 服务器端口
    :param max_retries: 最大重试次数
    :param initial_delay: 初始重试延迟（秒）
    :param max_delay: 最大延迟时间（秒）
    :return: 如果连接成功，返回 True；如果所有重试失败，返回 False
    """
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
            delay = min(delay * 2, max_delay)  # 指数回退，最大延迟为 max_delay

    logging.error(f"Failed to connect to LSP server at {host}:{port} after {max_retries} attempts.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    parser.add_argument('--port', type=int, required=True, help="Port for the pylsp server.")

    args = parser.parse_args()
    
    pylsp_process = start_pylsp(args.port)
    lspport = args.port
    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    root_uri = f"file://{repo_path}"
    graph_path = os.path.join(results_dir, 'repoparser.json')
    try:
        with open(graph_path, 'r') as f:
            graph = nx.node_link_graph(json.load(f))
    except FileNotFoundError:
        logging.debug(f"Graph file not found: {graph_path}")
        return
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        logging.info(f"Connecting to LSP server on port {lspport}")
        if not connect_with_exponential_backoff(sock, LSP_HOST, lspport):
            logging.error("Cannot connect to LSP server.")
            return

        sock.settimeout(20.0)
        
        response_thread = threading.Thread(target=receive_response, args=(sock,))
        response_thread.daemon = True
        response_thread.start()
        
        initialize(sock, root_uri)
        initialized.wait()

        process_ast_nodes(sock, graph)
        #覆盖repoparser.json
        output_path = os.path.join(results_dir, 'definitiongraph.json')
        with open(output_path, 'w') as f:
            json.dump(nx.node_link_data(graph), f, indent=4)
        #从文件系统里删除 repo_parser.json
        os.remove(graph_path)
            # 结束 pylsp 进程
        pylsp_process.terminate()  # 停止 pylsp 子进程
        pylsp_process.wait()  # 等待 pylsp 进程退出



if __name__ == "__main__":
    main()
