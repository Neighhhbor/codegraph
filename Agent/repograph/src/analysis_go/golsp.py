import socket
import json
import os
import networkx as nx
import logging
import re
import threading
import queue
from tqdm import tqdm
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

LSP_HOST = 'localhost'
LSP_PORT = 8080  # Replace with the actual gopls port if different

opened_files = set()
request_id = 1
pending_requests = {}  # For storing pending requests
response_queue = queue.Queue()  # For storing incoming responses

# Create a Lock for thread-safe operations on shared resources
pending_requests_lock = threading.Lock()

# Helper function to send requests
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

# Helper function to read exact number of bytes from the socket
def read_exact(sock, nbytes):
    data = b''
    while len(data) < nbytes:
        more = sock.recv(nbytes - len(data))
        if not more:
            raise EOFError(f'Expected {nbytes} bytes but only received {len(data)} bytes before the connection closed.')
        data += more
    return data

# Function to receive responses in a separate thread and put them into the queue
def receive_response(sock):
    """Receive a response from the server and parse the full JSON-RPC message."""
    sock.settimeout(30.0)  # Set a longer timeout to handle initialization delays
    while True:
        try:
            # Read the header first to get the content length
            header = ""
            while "\r\n\r\n" not in header:
                header += sock.recv(1).decode('utf-8')

            # Extract Content-Length from the header
            match = re.search(r"Content-Length: (\d+)", header)
            if not match:
                logging.error(f"Malformed header: {header}")
                continue

            content_length = int(match.group(1))
            # Read the content based on Content-Length
            content = read_exact(sock, content_length).decode('utf-8')

            try:
                message = json.loads(content)
                logging.debug(f"Received Message:\n{json.dumps(message, indent=2)}")

                # Simply place the received message into the response queue
                response_queue.put(message)
            except json.JSONDecodeError as e:
                logging.error(f"JSON Decode Error: {content} - {e}")
        except socket.timeout as e:
            logging.warning(f"Socket timeout while receiving response: {e}")
            return None

# Function to send request and block until response is received
def send_request_and_wait(sock, message):
    send_request(sock, message)

    # Wait for the response to match the request id
    while True:
        response = response_queue.get()  # Block until we get a response
        logging.debug(f"Processing response: {json.dumps(response, indent=2)}")

        # Check if the response id matches the request id
        if "id" in response:
            if response["id"] == message["id"]:
                logging.debug(f"Received response for request ID {message['id']}")
                with pending_requests_lock:
                    if message["id"] in pending_requests:
                        del pending_requests[message["id"]]
                return response
        else:
            # If the id doesn't match, put the response back into the queue
            response_queue.put(response)

# Initialize function
def initialize(sock, root_uri):
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
    response = send_request_and_wait(sock, message)
    if response and "result" in response:
        logging.info("Go Language Server initialized successfully.")
        send_initialized_notification(sock)
    else:
        logging.error("Failed to initialize Go Language Server.")

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
                "languageId": "go",
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
    response = send_request_and_wait(sock, message)
    logging.debug(f"Definition request response: {response}")
    if response and "result" in response:
        return response["result"]
    return None

def request_references(sock, file_uri, position):
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/references",
        "params": {
            "textDocument": {"uri": file_uri},
            "position": position
        }
    }
    response = send_request_and_wait(sock, message)
    logging.debug(f"References request response: {response}")
    if response and "result" in response:
        return response["result"]
    return None

def request_links(sock, file_uri):
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/documentLink",
        "params": {"textDocument": {"uri": file_uri}}
    }
    response = send_request_and_wait(sock, message)
    logging.debug(f"Links request response: {response}")
    if response and "result" in response:
        return response["result"]
    return None

def request_declaration(sock, file_uri, position):
    message = {
        "jsonrpc": "2.0",
        "method": "textDocument/declaration",
        "params": {"textDocument": {"uri": file_uri}, "position": position}
    }
    response = send_request_and_wait(sock, message) 
    logging.debug(f"Declaration request response: {response}")
    if response and "result" in response:
        return response["result"]
    return None

def request_call_hierarchy(sock, file_uri, position):
   # Step 1: Prepare call hierarchy
    prepare_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "textDocument/prepareCallHierarchy",
        "params": {
            "textDocument": {"uri": file_uri},
            "position": position
        }
    }
    prepare_response = send_request_and_wait(sock, prepare_message)
    
    if prepare_response is None or "result" not in prepare_response:
        return None  # Failed to prepare call hierarchy

    hierarchy_items = prepare_response["result"]
    if hierarchy_items is None:
        return None
    call_hierarchy_info = []

    # Step 2 & 3: For each item, get incoming and outgoing calls
    for item in hierarchy_items:
        # Incoming calls
        incoming_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "callHierarchy/incomingCalls",
            "params": {
                "item": item
            }
        }
        incoming_response = send_request_and_wait(sock, incoming_message)
        incoming_calls = incoming_response["result"] if incoming_response and "result" in incoming_response else []

        # Outgoing calls
        outgoing_message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "callHierarchy/outgoingCalls",
            "params": {
                "item": item
            }
        }
        outgoing_response = send_request_and_wait(sock, outgoing_message)
        outgoing_calls = outgoing_response["result"] if outgoing_response and "result" in outgoing_response else []

        # Collect call hierarchy info for the current item
        call_hierarchy_info.append({
            "item": item,
            "incoming_calls": incoming_calls,
            "outgoing_calls": outgoing_calls
        })

    return call_hierarchy_info if call_hierarchy_info else None
# Process AST nodes and request symbol definitions
def process_ast_nodes(sock, graph):
    total_nodes = len(graph.nodes)

    with tqdm(total=total_nodes, desc="Processing AST Nodes", unit="node") as pbar:
        for node_id, node_data in graph.nodes(data=True):
            if node_data.get("is_named", False):
                file_id = node_data["file_id"]
                file_path = graph.nodes[file_id]["path"]
                file_uri = f"file://{file_path}"

                position = {
                    "line": node_data["start_point"][0],
                    "character": node_data["start_point"][1]
                }

                if file_uri not in opened_files:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    did_open_file(sock, file_uri, content)
                    opened_files.add(file_uri)

                definition_result = request_definition(sock, file_uri, position)
                node_data["definition"] = definition_result
                references_result = request_references(sock, file_uri, position)
                node_data["references"] = references_result
                declaration_result = request_declaration(sock, file_uri, position)
                node_data["declaration"] = declaration_result
                call_hierarchy_result = request_call_hierarchy(sock, file_uri, position)
                node_data["call_hierarchy"] = call_hierarchy_result
            elif node_data["type"] in ["file"]:
                file_uri = f"file://{node_data['path']}"
                links_result = request_links(sock, file_uri)
                node_data["links"] = links_result

            pbar.update(1)

# Main function to run the script
def main():
    parser = argparse.ArgumentParser(description="Parse a source code repository and generate its representation graph.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    root_uri = f"file://{repo_path}"
    graph_path = os.path.join(results_dir, 'repoparser.json')
    
    try:
        with open(graph_path, 'r') as f:
            graph = nx.node_link_graph(json.load(f), edges="links")
    except FileNotFoundError:
        logging.error(f"Graph file not found: {graph_path}")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((LSP_HOST, LSP_PORT))
        except ConnectionRefusedError:
            logging.error("Cannot connect to LSP server.")
            return

        sock.settimeout(5.0)

        # Start the response listener thread
        response_thread = threading.Thread(target=receive_response, args=(sock,))
        response_thread.daemon = True
        response_thread.start()

        initialize(sock, root_uri)
        process_ast_nodes(sock, graph)
        logging.info(f"pending_requests number: {len(pending_requests)}")
        for request_id, request in pending_requests.items():
            logging.debug(f"pending_requests: {request_id} - {request}")
        output_path = os.path.join(results_dir, 'definitiongraph.json')
        with open(output_path, 'w') as f:
            json.dump(nx.node_link_data(graph, edges="links"), f, indent=4)
        logging.info(f"Definition graph saved to {output_path}")

if __name__ == "__main__":
    main()
