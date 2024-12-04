import os
import subprocess
import argparse
import multiprocessing
import json
import logging

def is_port_available(port):
    """检查端口是否被占用，且没有进行端口转发"""
    cmd = f"netstat -tulpn | grep :{port}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        # 如果 netstat 返回了该端口的占用信息，端口已被占用或转发
        return False
    return True

def get_free_ports(start_port, num_ports=1):
    """获取多个空闲端口"""
    ports = []
    port = start_port
    while len(ports) < num_ports:
        if is_port_available(port):
            ports.append(port)
        port += 1  # 如果当前端口被占用，则尝试下一个端口
    return ports


def run_script(script_name, args):
    """运行指定的脚本，传递参数"""
    cmd = ["python", script_name] + args
    subprocess.run(cmd, check=True)

def process_repo(repo_path, result_dir, ports):
    """处理一个repo，按顺序运行多个脚本"""
    try:
        repo_name = os.path.basename(repo_path.rstrip('/'))
        result_repo_dir = os.path.join(result_dir, repo_name)
        logging.info(f"Processing repo: {repo_path} with ports {ports}")
        # 判断是否已经处理过
        output_file = os.path.join(result_repo_dir, f"{repo_name}.json")
        if os.path.exists(result_repo_dir) and os.path.exists(output_file):
            print(f"Repo {repo_name} already processed, skipping...")
            return
        
        print(f"Starting processing repo: {repo_path} with ports {ports}")
        
        # 依次运行脚本
        run_script("pipeline.py", [repo_path, "--output_dir", result_dir, "--ports"]+list(map(str, ports)))
        
        print(f"Finished processing repo: {repo_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_path}: {e}")

def assign_ports_and_process_repos(dev_eval_path, result_dir, max_workers, ports_per_repo):
    """遍历 DevEval 目录下的每个 repo，并进行并行处理"""
    # 获取所有repo路径
    categories = [os.path.join(dev_eval_path, category) for category in os.listdir(dev_eval_path) if os.path.isdir(os.path.join(dev_eval_path, category))]
    
    repo_paths = []
    for category in categories:
        repo_paths += [os.path.join(category, repo) for repo in os.listdir(category) if os.path.isdir(os.path.join(category, repo))]

    # 获取空闲端口
    start_port = 5000  # 假设从端口5000开始分配
    all_ports = []
    
    for _ in range(len(repo_paths)):
        free_ports = get_free_ports(start_port, ports_per_repo)
        all_ports.append(free_ports)
        logging.info(f"Assigned ports: {free_ports}")
        start_port = free_ports[-1] + 1  # 下一个仓库使用下一个端口开始

    # 使用进程池并行处理任务
    with multiprocessing.Pool(processes=max_workers) as pool:
        pool.starmap(process_repo, [(repo_path, result_dir, ports) for repo_path, ports in zip(repo_paths, all_ports)])
    
    print("Finished processing all repos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process repositories in DevEval with parallelism.")
    parser.add_argument("dev_eval_path", type=str, help="Path to the DevEval directory.")
    parser.add_argument("result_dir", type=str, help="Directory to store the result outputs.")
    parser.add_argument("--max_workers", type=int, default=8, help="Maximum number of parallel tasks to run at once.")
    parser.add_argument("--ports_per_repo", type=int, default=4, help="Number of ports to assign to each repo.")
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.result_dir, exist_ok=True)
    
    # 处理所有的 repo，并进行并行处理
    assign_ports_and_process_repos(args.dev_eval_path, args.result_dir, args.max_workers, args.ports_per_repo)
