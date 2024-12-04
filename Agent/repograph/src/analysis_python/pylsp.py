import socket
import json
import os
import time
import networkx as nx
import re
import asyncio
import logging
import subprocess
import argparse
from tqdm import tqdm

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='pylsp.log',
    filemode='w'
)

LSP_HOST = 'localhost'
opened_files = set()
MAX_OPEN_FILES = 20

# Define LSPConnection class
class LSPConnection:
    def __init__(self, host, port, connection_id):
        self.host = host
        self.port = port
        self.connection_id = connection_id
        self.reader = None
        self.writer = None
        self.request_id = 1
        self.pending_requests = {}
        self.response_queue = asyncio.Queue()
        self.initialized = asyncio.Event()
        self.logger = logging.getLogger(f"LSPConnection-{self.connection_id}")
    
    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        asyncio.create_task(self.receive_response())
        self.logger.info(f"Connected to LSP server at {self.host}:{self.port}")
    
    async def send_request(self, message):
        message["id"] = self.request_id
        current_id = self.request_id
        self.pending_requests[current_id] = asyncio.Event()
        self.request_id += 1

        message_str = json.dumps(message)
        content_length = len(message_str)
        header = f"Content-Length: {content_length}\r\n\r\n"
        full_message = header + message_str
        self.logger.debug(f"Sending Request (ID: {current_id}):\n{message_str}...")

        try:
            self.writer.write(full_message.encode('utf-8'))
            await self.writer.drain()
        except Exception as e:
            self.logger.error(f"Error while sending request ID {current_id}: {e}")
            del self.pending_requests[current_id]
            return None
        return current_id

    async def receive_response(self):
        while True:
            try:
                header = ""
                while "\r\n\r\n" not in header:
                    char = await self.reader.read(1)
                    if not char:
                        raise EOFError("Connection closed while reading header")
                    header += char.decode('utf-8')

                match = re.search(r"Content-Length: (\d+)", header)
                if not match:
                    self.logger.error(f"Malformed header: {header}")
                    continue

                content_length = int(match.group(1))
                content = await self.reader.readexactly(content_length)
                message = json.loads(content.decode('utf-8'))
                self.logger.debug(f"Received Message:\n{json.dumps(message, indent=2)}")

                if "id" in message:
                    await self.response_queue.put(message)
                    if message["id"] in self.pending_requests:
                        self.pending_requests[message["id"]].set()
            except asyncio.IncompleteReadError as e:
                self.logger.error(f"Incomplete read error: {e}")
                break
            except EOFError as e:
                self.logger.error(f"EOFError: {e}")
                break
            except Exception as e:
                self.logger.error(f"Error while receiving response: {e}")
                break

    async def send_request_and_wait(self, message, retries=3):
        for attempt in range(retries):
            req_id = await self.send_request(message)
            if req_id is None:
                continue
            try:
                await asyncio.wait_for(self.pending_requests[req_id].wait(), timeout=3)
            except asyncio.TimeoutError:
                self.logger.warning(f"Request ID {req_id} timed out on attempt {attempt + 1}")
                del self.pending_requests[req_id]
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue

            while not self.response_queue.empty():
                msg = await self.response_queue.get()
                if msg.get("id") == req_id:
                    if "result" in msg:
                        del self.pending_requests[req_id]
                        return msg["result"]
                    else:
                        del self.pending_requests[req_id]
                        return None
        self.logger.error(f"Failed to get a response after {retries} attempts for message: {message}")
        return None

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.logger.info(f"Closed connection to LSP server at {self.host}:{self.port}")

# Start pylsp server
def start_pylsp(port):
    """启动 pylsp 进程，并为其指定端口"""
    cmd = ['jedi-language-server', '--tcp', '--host', '127.0.0.1', '--port', str(port)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.info(f"Started pylsp process on port {port}")
    return process

# Initialize a single LSP connection
async def initialize_connection(connection, root_uri):
    message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {},
            "workspaceFolders": [{"uri": root_uri, "name": "Workspace"}],
        }
    }
    response = await connection.send_request_and_wait(message, retries=5)
    if response:
        connection.logger.info("Python Language Server initialized successfully.")
        await send_initialized_notification(connection)
        connection.initialized.set()
    else:
        connection.logger.error("Failed to initialize Python Language Server.")

# Send initialized notification
async def send_initialized_notification(connection):
    message = {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {}
    }
    await connection.send_request(message)

# Handle a single node
async def handle_node(connection, node_data, file_uri, position, progress_bar, semaphore):
    async with semaphore:
        result = await connection.send_request_and_wait({
            "jsonrpc": "2.0",
            "method": "textDocument/definition",
            "params": {
                "textDocument": {"uri": file_uri},
                "position": position
            }
        }, retries=3)
        if result is not None:
            node_data["definition"] = result
        else:
            connection.logger.info(f"Skipping node {node_data} due to repeated timeouts.")
        progress_bar.update(1)

# Process AST nodes with multiple LSP connections
async def process_ast_nodes(lsp_connections, graph):
    total_nodes = len(graph.nodes)
    batch_size = 500  # 每批处理的节点数量
    max_concurrent = 100  # 最大并发任务数
    num_connections = len(lsp_connections)
    current_connection = 0  # 轮询索引

   
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = []

    target_nodes = [ (node_id, data) for node_id, data in graph.nodes(data=True)
                     if data.get("type") == 'identifier' and data.get("field_name") in ['function', 'attribute'] ]
    progress_bar = tqdm(total=len(target_nodes), desc="Processing definitions", ncols=100)
    for i, (node_id, node_data) in enumerate(target_nodes):
            file_id = node_data["file_id"]
            file_path = graph.nodes[file_id]["path"]
            file_uri = f"file://{file_path}"

            position = {
                "line": node_data["sp"][0],
                "character": node_data["sp"][1]
            }

            # 选择一个 LSP 连接（轮询）
            connection = lsp_connections[current_connection]
            current_connection = (current_connection + 1) % num_connections

            # 打开文件（如果尚未打开）
            if file_uri not in opened_files:
                with open(file_path, 'r') as f:
                    content = f.read()
                for connection in lsp_connections:
                    await connection.send_request({
                        "jsonrpc": "2.0",
                        "method": "textDocument/didOpen",
                        "params": {
                            "textDocument": {
                                "uri": file_uri,
                            "languageId": "python",
                            "version": 1,
                            "text": content
                            }
                        }
                    })
                opened_files.add(file_uri)

            # 创建处理节点的任务
            task = asyncio.create_task(handle_node(connection, node_data, file_uri, position, progress_bar, semaphore))
            tasks.append(task)

            if len(tasks) >= batch_size:
                await asyncio.gather(*tasks)
                tasks = []
                await asyncio.sleep(0.1)  # 轻微的暂停，防止服务器过载

    if tasks:
        await asyncio.gather(*tasks)

    progress_bar.close()

# Main function
async def main():
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    parser.add_argument('--ports', type=int, nargs='+', default=[3000, 3001], help="Ports of the LSP servers.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    output_path = os.path.join(results_dir, 'definitiongraph.json')
    if os.path.exists(output_path):
        return
    root_uri = f"file://{repo_path}"
    graph_path = os.path.join(results_dir, 'repoparser.json')

    try:
        with open(graph_path, 'r') as f:
            graph = nx.node_link_graph(json.load(f))
    except FileNotFoundError:
        logger.debug(f"Graph file not found: {graph_path}")
        return

    # 启动多个 pylsp 进程
    # "3001 3002"
    lsp_ports = list(map(int, args.ports))

    lsp_processes = []
    for port in lsp_ports:
        process = start_pylsp(port)
        lsp_processes.append(process)
    await asyncio.sleep(2)  # 等待所有 pylsp 启动

    # 创建多个 LSP 连接
    lsp_connections = []
    for idx, port in enumerate(lsp_ports):
        connection = LSPConnection(LSP_HOST, port, connection_id=idx)
        await connection.connect()
        lsp_connections.append(connection)

    try:
        # 初始化所有 LSP 连接
        initialize_tasks = [initialize_connection(connection, root_uri) for connection in lsp_connections]
        logger.info(f"Initializing {len(initialize_tasks)} LSP connections...")
        await asyncio.gather(*initialize_tasks)

        # 处理 AST 节点，分配给不同的 LSP 连接
        await process_ast_nodes(lsp_connections, graph)

        # 保存最终结果
       
        with open(output_path, 'w') as f:
            json.dump(nx.node_link_data(graph), f, indent=4)
        logger.info(f"Definition graph saved to {output_path}")

    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        # 关闭所有 LSP 连接
        close_tasks = [connection.close() for connection in lsp_connections]
        await asyncio.gather(*close_tasks)

        # 终止所有 pylsp 进程
        for process in lsp_processes:
            process.terminate()
            process.wait()
            logger.info(f"Terminated pylsp process on port {process.args[-1]}")
        os.remove(graph_path)

async def pylsp_main(graph, repo_path, output_dir, ports):
    root_uri = f"file://{repo_path}"
    lsp_ports = ports

    lsp_processes = []
    for port in lsp_ports:
        process = start_pylsp(port)
        lsp_processes.append(process)
    await asyncio.sleep(2)  # 等待所有 pylsp 启动

    # 创建多个 LSP 连接
    lsp_connections = []
    for idx, port in enumerate(lsp_ports):
        connection = LSPConnection(LSP_HOST, port, connection_id=idx)
        await connection.connect()
        lsp_connections.append(connection)

    try:
        # 初始化所有 LSP 连接
        initialize_tasks = [initialize_connection(connection, root_uri) for connection in lsp_connections]
        logger.info(f"Initializing {len(initialize_tasks)} LSP connections...")
        await asyncio.gather(*initialize_tasks)

        # 处理 AST 节点，分配给不同的 LSP 连接
        await process_ast_nodes(lsp_connections, graph)


    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        # 关闭所有 LSP 连接
        close_tasks = [connection.close() for connection in lsp_connections]
        await asyncio.gather(*close_tasks)

        # 终止所有 pylsp 进程
        for process in lsp_processes:
            process.terminate()
            process.wait()
            logger.info(f"Terminated pylsp process on port {process.args[-1]}")

        return graph

if __name__ == "__main__":
    asyncio.run(main())