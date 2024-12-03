import json
import os
import networkx as nx
import asyncio
import logging
import argparse
from tqdm import tqdm
import jedi
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,  # 设置为DEBUG以获取详细日志，生产环境中可设置为INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='jedi_definition.log',
    filemode='w'  # 使用写入模式，避免追加
)

class JediHandler:
    def __init__(self, file_contents, max_workers=10):
        """
        初始化Jedi处理器，使用ThreadPoolExecutor进行并行处理。
        
        :param file_contents: 字典，键为文件路径，值为文件内容
        :param max_workers: 最大工作线程数
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        # self.cache = {}  # 缓存定义结果，键为 (file_path, line, column)
        self.file_contents = file_contents
        logger.info(f"Initialized JediHandler with {max_workers} workers.")
        # 禁用 fast_parser 以确保线程安全
        self.original_fast_parser = jedi.settings.fast_parser
        jedi.settings.fast_parser = False

    def get_definition(self, file_path, line, column):
        """
        使用jedi查找定义，并缓存结果。
        
        :param file_path: 文件路径
        :param line: 行号（1-based）
        :param column: 列号（0-based）
        :return: 定义信息列表
        """
        source = self.file_contents.get(file_path)
        if source is None:
            logger.error(f"No preloaded content for file: {file_path}")
        try:
            script = jedi.Script(code=source, path="example.py")
            definitions = script.goto(line+1, column)
            # logger.debug(f"Definitions returned : {definitions}")
            # line,col = definitions[0].get_definition_start_position()
            definitions_info = []
            # for d in definitions:
            #     # d is an instance of jedi.api.classes.Name
            definitions_info.append({
                    'name': "fake",
                    'module': "fake",
                    'line': 1,
                    'column': 1,
                    "position": (1,1)
                })
            logger.debug(f"Definitions info: {definitions_info}")
            return 
        except Exception as e:
            logger.error(f"Error finding definition for {file_path} at ({line}, {column}): {type(e)}")

    async def get_definition_async(self, file_path, line, column):
        """
        异步调用get_definition方法。
        
        :param file_path: 文件路径
        :param line: 行号（1-based）
        :param column: 列号（0-based）
        :return: 定义信息列表
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.get_definition,
            file_path,
            line,
            column
        )

    def shutdown(self):
        """
        关闭ThreadPoolExecutor并恢复fast_parser设置。
        """
        self.executor.shutdown(wait=True)
        jedi.settings.fast_parser = self.original_fast_parser
        logger.info("JediHandler executor shutdown completed and fast_parser restored.")

async def process_node(jedi_handler, node_data, file_path, position, progress_bar):
    """
    处理单个节点，使用jedi查找定义并更新节点数据。
    
    :param jedi_handler: JediHandler实例
    :param node_data: 节点数据字典
    :param file_path: 文件路径
    :param position: 字典，包含'line'和'character'
    :param progress_bar: tqdm进度条实例
    """
    definitions = await jedi_handler.get_definition_async(
        file_path,
        position['line'],
        position['character']
    )
    if definitions:
        node_data["definition"] = definitions
        logger.debug(f"Added definitions to node {node_data['id']}")
    else:
        logger.info(f"Skipping node {node_data['id']} in {file_path} at ({position['line']}, {position['character']}) due to no definition found.")
    progress_bar.update(1)

async def process_ast_nodes(jedi_handler, graph, file_contents, max_nodes=None):
    """
    处理所有目标节点，使用jedi查找定义并更新图数据。
    
    :param jedi_handler: JediHandler实例
    :param graph: networkx图实例
    :param file_contents: 字典，键为file_path，值为文件内容
    :param max_nodes: 最大处理节点数，用于调试
    """
    total_nodes = len(graph.nodes)
    logger.info(f"Total nodes in graph: {total_nodes}")
    target_nodes = [ (node_id, data) for node_id, data in graph.nodes(data=True)
                     if data.get("type") == 'identifier' and data.get("field_name") in ['function', 'attribute'] ]
    logger.info(f"Total target nodes to process: {len(target_nodes)}")

    # 如果设置了 max_nodes，仅处理前 max_nodes 个节点
    if max_nodes:
        target_nodes = target_nodes[:max_nodes]
        logger.info(f"Processing first {max_nodes} nodes for debugging.")

    batch_size = 1000  # 每批处理的节点数量，根据需要调整
    max_concurrent = 100  # 最大并发任务数，根据需要调整

    progress_bar = tqdm(total=len(target_nodes), desc="Processing nodes", ncols=100)
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = []

    for node_id, node_data in target_nodes:
        file_id = node_data.get("file_id")
        if not file_id:
            logger.error(f"Node {node_id} missing 'file_id'. Skipping.")
            progress_bar.update(1)
            continue

        file_node = graph.nodes[file_id]
        file_path = file_node.get("path")
        if not file_path:
            logger.error(f"File ID {file_id} missing 'path'. Skipping node {node_id}.")
            progress_bar.update(1)
            continue
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}. Skipping node {node_id}.")
            progress_bar.update(1)
            continue

        position = {
            "line": node_data.get("sp")[0],  # 默认行1，列0
            "character": node_data.get("sp")[1]
        }
        # logger.debug(f"Processing node {node_id} in {file_path} at ({position['line']}, {position['character']})")

        async def bound_process(node_id, node_data, file_path, position):
            async with semaphore:
                await process_node(jedi_handler, node_data, file_path, position, progress_bar)

        task = asyncio.create_task(bound_process(node_id, node_data, file_path, position))
        tasks.append(task)

        if len(tasks) >= batch_size:
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = []
            await asyncio.sleep(0.1)  # 轻微的暂停，防止过载

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    progress_bar.close()
    logger.info("All target nodes processed.")

async def preload_files_async(graph):
    """
    预加载所有相关文件的内容。
    
    :param graph: networkx图实例
    :return: 字典，键为file_path，值为文件内容
    """
    file_contents = {}
    file_ids = { data.get('file_id') for _, data in graph.nodes(data=True) if data.get('file_id') is not None }
    logger.info(f"Preloading {len(file_ids)} files.")
    for file_id in file_ids:
        if file_id not in graph.nodes:
            logger.error(f"File node {file_id} not found in graph. Skipping.")
            continue

        file_node = graph.nodes[file_id]
        file_path = file_node.get("path")
        if not file_path:
            logger.error(f"File ID {file_id} missing 'path'. Skipping.")
            continue
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}. Skipping.")
            continue
        try:
            # 使用异步方式读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            file_contents[file_path] = content
            logger.debug(f"Preloaded file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            # 可以选择在这里抛出异常，或者继续
            # raise
    logger.info(f"Preloaded {len(file_contents)} files successfully.")
    return file_contents

def main():
    parser = argparse.ArgumentParser(description="Find definitions of specific nodes using Jedi.")
    parser.add_argument('repo_path', type=str, help="Path to the repository to be parsed.")
    parser.add_argument('--output_dir', type=str, default="./output", help="Directory where the output will be saved.")
    parser.add_argument('--max_nodes', type=int, default=None, help="Maximum number of nodes to process for debugging.")
    args = parser.parse_args()

    repo_path = args.repo_path
    results_dir = os.path.join(args.output_dir, os.path.basename(repo_path.rstrip('/')))
    os.makedirs(results_dir, exist_ok=True)
    graph_path = os.path.join(results_dir, 'repoparser.json')
    output_path = os.path.join(results_dir, 'definitiongraph.json')

    try:
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        graph = nx.node_link_graph(graph_data)
        logger.info(f"Loaded graph from {graph_path}. Total nodes: {len(graph.nodes)}.")
    except FileNotFoundError:
        logger.error(f"Graph file not found: {graph_path}. Exiting.")
        return
    except Exception as e:
        logger.exception(f"Failed to load graph file {graph_path}. Exiting.")
        return

    # 预加载文件内容
    try:
        file_contents = asyncio.run(preload_files_async(graph))
    except Exception as e:
        logger.exception("Error during preloading files. Exiting.")
        return

    # 初始化Jedi处理器
    jedi_handler = JediHandler(file_contents, max_workers=20)  # 根据CPU核心数调整

    try:
        # 处理AST节点
        asyncio.run(process_ast_nodes(jedi_handler, graph, file_contents, max_nodes=args.max_nodes))

        # 保存最终结果
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(nx.node_link_data(graph), f, indent=4)
            logger.info(f"Definition graph saved to {output_path}.")
        except Exception as e:
            logger.exception(f"Failed to save definition graph to {output_path}.")
    except Exception as e:
        logger.exception("Error occurred during processing.")
    finally:
        # 关闭ThreadPoolExecutor并恢复fast_parser设置
        jedi_handler.shutdown()
        logger.info("JediHandler shutdown completed.")
        # 如果需要删除 graph_path 文件，可以保留，否则建议移除
        # os.remove(graph_path)

if __name__ == "__main__":
    main()
