import os
import subprocess
import argparse
import multiprocessing
import json
import logging

def run_script(script_name, args):
    """运行指定的脚本，传递参数"""
    cmd = ["python", script_name] + args
    subprocess.run(cmd, check=True)

def process_repo(repo_path, result_dir):
    """处理一个repo，按顺序运行多个脚本"""
    try:
        repo_name = os.path.basename(repo_path.rstrip('/'))
        result_repo_dir = os.path.join(result_dir, repo_name)
        
        # 判断是否已经处理过
        output_file = os.path.join(result_repo_dir, f"{repo_name}.json")
        if os.path.exists(result_repo_dir) and os.path.exists(output_file):
            print(f"Repo {repo_name} already processed, skipping...")
            return
        
        print(f"Starting processing repo: {repo_path}")
        
        # 依次运行脚本
        run_script("repo_parser.py", [repo_path, "--output_dir", result_dir])
        run_script("jedi_definition.py", [repo_path, "--output_dir", result_dir])
        run_script("defid_parser.py", [repo_path, "--output_dir", result_dir])
        run_script("funcid.py", [repo_path, "--output_dir", result_dir])
        run_script("relation_parser.py", [repo_path, "--output_dir", result_dir])
        run_script("extract.py", [repo_path, "--output_dir", result_dir])
        
        print(f"Finished processing repo: {repo_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_path}: {e}")

def assign_ports_and_process_repos(dev_eval_path, result_dir, max_workers):
    """遍历 DevEval 目录下的每个 repo，并进行并行处理"""
    # 获取所有repo路径
    categories = [os.path.join(dev_eval_path, category) for category in os.listdir(dev_eval_path) if os.path.isdir(os.path.join(dev_eval_path, category))]
    
    repo_paths = []
    for category in categories:
        repo_paths += [os.path.join(category, repo) for repo in os.listdir(category) if os.path.isdir(os.path.join(category, repo))]
    
    # 检查哪些 repo 已经处理过
    repo_to_process = []
    for repo_path in repo_paths:
        repo_name = os.path.basename(repo_path.rstrip('/'))
        result_repo_dir = os.path.join(result_dir, repo_name)
        output_file = os.path.join(result_repo_dir, f"{repo_name}.json")
        if not os.path.exists(result_repo_dir) or not os.path.exists(output_file):
            repo_to_process.append(repo_path)
        else:
            print(f"Repo {repo_name} already processed, skipping...")
    
    # 使用进程池并行处理任务
    with multiprocessing.Pool(processes=max_workers) as pool:
        pool.starmap(process_repo, [(repo_path, result_dir) for repo_path in repo_to_process])
    
    print("Finished processing all repos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process repositories in DevEval with parallelism.")
    parser.add_argument("dev_eval_path", type=str, help="Path to the DevEval directory.")
    parser.add_argument("result_dir", type=str, help="Directory to store the result outputs.")
    parser.add_argument("--max_workers", type=int, default=8, help="Maximum number of parallel tasks to run at once.")
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.result_dir, exist_ok=True)
    
    # 处理所有的 repo，并进行并行处理
    assign_ports_and_process_repos(args.dev_eval_path, args.result_dir, args.max_workers)
