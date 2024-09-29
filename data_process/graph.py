import os
import sys
import logging
from tqdm import tqdm  # 导入进度条库


# 动态添加模块路径
sys.path.append('/home/sxj/Desktop/Workspace/CodeQl/gptgraph/CodeGraph')  # 修改为实际路径

from code_graph import CodeGraph
from parsers.contains_parser import ContainsParser
from parsers.import_parser import ImportParser
from parsers.call_parser import CallParser
from lsp_client import LspClientWrapper

RESULTDIR = "./graphs"

# 全局日志配置
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def generate_code_graph(repo_path):
    """为给定的代码库生成 GML 文件。"""
    repo_name = os.path.basename(os.path.normpath(repo_path))
    logging.info(f"Processing repository: {repo_name}")

    # 第一步：解析 CONTAINS 关系
    contains_parser = ContainsParser(repo_path, repo_name)
    contains_parser.parse()

    # 构建代码图
    code_graph = CodeGraph()
    code_graph.build_graph_from_tree(contains_parser.root)

    # 第二步：解析 IMPORT 关系
    import_parser = ImportParser(repo_path, repo_name)
    import_parser.parse()
    for import_data in import_parser.imports:
        importer, imported_module = import_data
        code_graph.add_import(importer, imported_module)

    # 第三步：解析调用关系并启动 LSP 服务器
    lsp_client = LspClientWrapper(repo_path)
    lsp_client.start_server()

    try:
        call_parser = CallParser(repo_path, repo_name, code_graph, contains_parser.defined_symbols, lsp_client)
        call_parser.parse()

        for caller, callee in call_parser.calls:
            code_graph.add_call(caller, callee)
    finally:
        lsp_client.stop_server()

    # 保存代码图
    os.makedirs(RESULTDIR, exist_ok=True)
    gml_path = os.path.join(RESULTDIR, f"{repo_name}_code_graph.gml")
    code_graph.export_to_gml(gml_path)
    logging.info(f"Saved GML to: {gml_path}")

def process_repositories(base_dir):
    """遍历目录并为每个代码库生成 GML 文件。"""
    repos = []
    for category in os.listdir(base_dir):
        category_path = os.path.join(base_dir, category)
        if os.path.isdir(category_path):
            for repo in os.listdir(category_path):
                repo_path = os.path.join(category_path, repo)
                if os.path.isdir(repo_path):
                    repos.append(repo_path)

    # 使用 tqdm 显示进度条
    for repo_path in tqdm(repos, desc="Processing repositories"):
        generate_code_graph(repo_path)

def renamefiles(dir_path):  
    for file in os.listdir(dir_path):  
        if file.endswith('_code_graph.gml'):  # 确保只处理以'_code_graph.gml'结尾的文件
            newname = file.replace('_code_graph', '')  # 去掉'_code_graph'
            os.rename(os.path.join(dir_path, file), os.path.join(dir_path, newname))  
            print('已重命名文件：', newname)

# 示例用法
# renamefiles('/path/to/your/directory')

if __name__ == "__main__":
    # base_dir = '/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/Source_Code'  # 根据你的实际路径设置
    # process_repositories(base_dir)
    dir = "/home/sxj/Desktop/Workspace/CodeQl/gptgraph/data_process/graphs"
    renamefiles(dir)
