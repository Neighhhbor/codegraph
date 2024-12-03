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
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='oldpylsp.log',
    filemode='w'
)

LSP_HOST = 'localhost'
MAX_OPEN_FILES = 10
opened_files = set()

request_id = 1
pending_requests = {}

response_queue = asyncio.Queue()

initialized = asyncio.Event()

# Start pylsp server
def start_pylsp(port):
    """启动 pylsp 进程，并为其指定端口"""
    cmd = ['pylsp', '--tcp', '--host', '127.0.0.1', '--port', str(port)]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.info(f"Started pylsp process on port {port}")
    return process

async def send_request(writer, message):
    global request_id
    message["id"] = request_id
    current_id = request_id
    pending_requests[current_id] = asyncio.Event()
    request_id += 1

    message_str = json.dumps(message)
    content_length = len(message_str)
    header = f"Content-Length: {content_length}\r\n\r\n"
    full_message = header + message_str
    logger.debug(f"Sending Request (ID: {current_id}):\n{message_str}...")

    try:
        writer.write(full_message.encode('utf-8'))
        await writer.drain()
    except Exception as e:
        logger.error(f"Error while sending request ID {current_id}: {e}")
        del pending_requests[current_id]
        return None
    return current_id

async def read_exact(reader, nbytes):
    return await reader.readexactly(nbytes)

async def initialize(writer, root_uri):
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
    req_id = await send_request(writer, message)
    if req_id is None:
        logger.error("Failed to send initialize request.")
        return

    try:
        await asyncio.wait_for(pending_requests[req_id].wait(), timeout=10)
    except asyncio.TimeoutError:
        logger.error("Initialize request timed out.")
        return

    # Retrieve the response from the queue
    while not response_queue.empty():
        msg = await response_queue.get()
        if msg.get("id") == req_id:
            if "result" in msg:
                logger.info("Python Language Server initialized successfully.")
                await send_initialized_notification(writer)
                initialized.set()
            else:
                logger.error("Failed to initialize Python Language Server.")
            del pending_requests[req_id]
            break

async def send_initialized_notification(writer):
    message = {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {}
    }
    await send_request(writer, message)

async def did_open_file(writer, file_uri, content):
    message = {
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
    }
    await send_request(writer, message)

async def request_definition(writer, file_uri, position):
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/definition",
        "params": {
            "textDocument": {"uri": file_uri},
            "position": position
        }
    }
    req_id = await send_request(writer, message)
    if req_id is None:
        return None

    try:
        await asyncio.wait_for(pending_requests[req_id].wait(), timeout=10)
    except asyncio.TimeoutError:
        logger.error(f"Definition request ID {req_id} timed out.")
        return None

    while not response_queue.empty():
        msg = await response_queue.get()
        if msg.get("id") == req_id:
            if "result" in msg:
                logger.debug(f"Definition response for ID {req_id}: {msg['result']}")
                del pending_requests[req_id]
                return msg["result"]
            else:
                logger.error(f"Definition request ID {req_id} failed.")
                del pending_requests[req_id]
                return None

async def receive_response(reader):
    while True:
        try:
            header = ""
            while "\r\n\r\n" not in header:
                char = await reader.read(1)
                if not char:
                    raise EOFError("Connection closed while reading header")
                header += char.decode('utf-8')

            match = re.search(r"Content-Length: (\d+)", header)
            if not match:
                logger.error(f"Malformed header: {header}")
                continue

            content_length = int(match.group(1))
            content = await read_exact(reader, content_length)
            message = json.loads(content.decode('utf-8'))
            logger.debug(f"Received Message:\n{json.dumps(message, indent=2)}")

            if "id" in message:
                await response_queue.put(message)
                # Signal the waiting request
                if message["id"] in pending_requests:
                    pending_requests[message["id"]].set()
        except asyncio.IncompleteReadError as e:
            logger.error(f"Incomplete read error: {e}")
            break
        except EOFError as e:
            logger.error(f"EOFError: {e}")
            break
        except Exception as e:
            logger.error(f"Error while receiving response: {e}")
            break

async def send_request_and_wait(writer, message, retries=3):
    for attempt in range(retries):
        req_id = await send_request(writer, message)
        if req_id is None:
            continue
        try:
            await asyncio.wait_for(pending_requests[req_id].wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(f"Request ID {req_id} timed out on attempt {attempt + 1}")
            del pending_requests[req_id]
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            continue

        while not response_queue.empty():
            msg = await response_queue.get()
            if msg.get("id") == req_id:
                if "result" in msg:
                    del pending_requests[req_id]
                    return msg["result"]
                else:
                    del pending_requests[req_id]
                    return None
    logger.error(f"Failed to get a response after {retries} attempts for message: {message}")
    return None

async def handle_node(writer, node_data, file_uri, position, progress_bar, semaphore):
    async with semaphore:
        result = await request_definition(writer, file_uri, position)
        if result is not None:
            node_data["definition"] = result
        else:
            logger.info(f"Skipping node {node_data} due to repeated timeouts.")
        progress_bar.update(1)

async def process_ast_nodes(writer, graph):
    total_nodes = len(graph.nodes)
    batch_size = 500  # 每批处理的节点数量
    max_concurrent = 100  # 最大并发任务数

    progress_bar = tqdm(total=total_nodes, desc="Processing nodes", ncols=100)
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = []

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
                await did_open_file(writer, file_uri, content)
                opened_files.add(file_uri)

            tasks.append(handle_node(writer, node_data, file_uri, position, progress_bar, semaphore))

            if len(tasks) >= batch_size:
                await asyncio.gather(*tasks)
                tasks = []
                await asyncio.sleep(0.1)  # 轻微的暂停，防止服务器过载

    if tasks:
        await asyncio.gather(*tasks)

    progress_bar.close()

async def main():
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    parser.add_argument('--port', type=int, default=3000, help="Port of the LSP server.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    root_uri = f"file://{repo_path}"
    graph_path = os.path.join(results_dir, 'repoparser.json')

    try:
        with open(graph_path, 'r') as f:
            graph = nx.node_link_graph(json.load(f))
    except FileNotFoundError:
        logger.debug(f"Graph file not found: {graph_path}")
        return

    pylsp_process = start_pylsp(args.port)
    await asyncio.sleep(2)  # 等待 pylsp 启动

    try:
        reader, writer = await asyncio.open_connection(LSP_HOST, args.port)
    except Exception as e:
        logger.error(f"Failed to connect to LSP server: {e}")
        pylsp_process.terminate()
        return

    try:
        # 启动接收响应的协程
        asyncio.create_task(receive_response(reader))

        # 初始化 LSP
        await initialize(writer, root_uri)

        # 等待初始化完成
        await initialized.wait()

        # 处理 AST 节点
        await process_ast_nodes(writer, graph)

        # 保存最终结果
        output_path = os.path.join(results_dir, 'definitiongraph.json')
        with open(output_path, 'w') as f:
            json.dump(nx.node_link_data(graph), f, indent=4)
        logger.info(f"Definition graph saved to {output_path}")

    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        pylsp_process.terminate()

if __name__ == "__main__":
    asyncio.run(main())
