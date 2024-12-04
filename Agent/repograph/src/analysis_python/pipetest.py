from repo_parser import repo_parser_main
from pylsp import pylsp_main
from newdef import defid_main
from relation_parser import relation_parser_main
from funcid import funcid_main
from extract import extract_main
import logging
import argparse
import asyncio
import networkx as nx
import json
import os


logger = logging.getLogger(__name__)

def save_graph(graph, output_path):
    """
    将处理后的图保存为 JSON 文件。
    """
    try:
        data = nx.node_link_data(graph)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"图已成功保存到: {output_path}")
    except Exception as e:
        logger.error(f"保存图时出错: {e}")
        
        
# Pipeline Main
async def pipeline_main(repo_path, output_dir, ports):
    """
    Main pipeline to process the repository and its graph.
    """
    repo_path = repo_path
    results_dir = os.path.join(output_dir, os.path.basename(repo_path))
    os.makedirs(results_dir, exist_ok=True)
    reponame = os.path.basename(repo_path)
    output_path = os.path.join(results_dir, f'{reponame}.json')
    # if os.path.exists(output_path):
    #     logger.info(f"图已存在: {output_path}")
    #     return
    
    # Step 1: RepoParser
    graph = repo_parser_main(repo_path, output_dir)

    # Step 2: PyLSP processing
    graph = await pylsp_main(graph, repo_path, output_dir, ports)
    save_graph(graph, os.path.join(results_dir, "Pylsp.json"))
    # Step 3: Add Definition IDs
    graph = defid_main(graph, repo_path, output_dir)
    save_graph(graph, os.path.join(results_dir, "Defid.json"))
    # Step 4: Add Function IDs
    graph = funcid_main(graph, repo_path, output_dir)
    save_graph(graph, os.path.join(results_dir, "Funcid.json"))
    # Step 5: Build Relationships
    graph = relation_parser_main(graph, repo_path, output_dir)
    save_graph(graph, os.path.join(results_dir, "Relation.json"))
    # Step 6: Extract Skeleton
    skeleton = extract_main(graph, repo_path, output_dir)
    save_graph(skeleton, output_path)
    logger.info("Pipeline processing completed successfully.")



def main():
    parser = argparse.ArgumentParser(description="Process a source code repository pipeline.")
    parser.add_argument("repo_path", type=str, help="Path to the source code repository.")
    parser.add_argument("--output_dir", type=str, default="./output", help="Output directory.")
    parser.add_argument("--ports", type=int, nargs="+", default=[4000, 4001, 4002, 4003], help="Ports for LSP servers.")
    args = parser.parse_args()

    asyncio.run(pipeline_main(args.repo_path, args.output_dir, args.ports))

if __name__ == "__main__":
    main()
