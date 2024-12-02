import os
import subprocess
import argparse
import multiprocessing
import socket
import time

def is_port_available(port):
    """检查端口是否被占用，且没有进行端口转发"""
    cmd = f"netstat -tulpn | grep :{port}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        # 如果 netstat 返回了该端口的占用信息，端口已被占用或转发
        return False
    return True

def get_free_port(start_port, num_ports=1):
    """获取多个空闲端口"""
    ports = []
    port = start_port
    while len(ports) < num_ports:
        if is_port_available(port):
            ports.append(port)
        port += 1  # 如果当前端口被占用，则尝试下一个端口
    return ports

def run_repo_parser(repo_path, result_dir):
    """运行 repo_parser.py 脚本"""
    print(f"Running repo_parser.py for {repo_path}")
    cmd = [
        "python", "repo_parser.py", repo_path, "--output_dir", result_dir
    ]
    subprocess.run(cmd, check=True)

def run_pylsp(repo_path, result_dir, ports):
    """运行 pylsp.py 脚本"""
    print(f"Running pylsp.py for {repo_path} on ports {ports}")
    cmd = [
        "python", "pylsp.py", repo_path, "--output_dir", result_dir, "--ports", *map(str, ports)
    ]
    subprocess.run(cmd, check=True)

def run_defid_parser(repo_path, result_dir):
    """运行 defid_parser.py 脚本"""
    print(f"Running defid_parser.py for {repo_path}")
    cmd = [
        "python", "defid_parser.py", repo_path, "--output_dir", result_dir
    ]
    subprocess.run(cmd, check=True)

def run_funcid_parser(repo_path, result_dir):
    """运行 funcid.py 脚本"""
    print(f"Running funcid.py for {repo_path}")
    cmd = [
        "python", "funcid.py", repo_path, "--output_dir", result_dir
    ]
    subprocess.run(cmd, check=True)

def run_relation_parser(repo_path, result_dir):
    """运行 relation_parser.py 脚本"""
    print(f"Running relation_parser.py for {repo_path}")
    cmd = [
        "python", "relation_parser.py", repo_path, "--output_dir", result_dir
    ]
    subprocess.run(cmd, check=True)

def run_extract(repo_path, result_dir):
    """运行 extract.py 脚本"""
    print(f"Running extract.py for {repo_path}")
    cmd = [
        "python", "extract.py", repo_path, "--output_dir", result_dir
    ]
    subprocess.run(cmd, check=True)

def process_repo(repo_path, result_dir, ports):
    """处理一个repo，按顺序运行多个脚本"""
    try:
        repo_name = os.path.basename(repo_path)
        result_repo_dir = os.path.join(result_dir, repo_name)
        
        if os.path.exists(result_repo_dir) and os.path.exists(os.path.join(result_repo_dir, f"{repo_name}.json")):
            print(f"Repo {repo_name} already processed, skipping...")
            return
        
        print(f"Starting processing repo: {repo_path} on port {ports}")
        
        # 依次运行脚本
        run_repo_parser(repo_path, result_dir)
        run_pylsp(repo_path, result_dir, ports)  # 处理多个端口
        run_defid_parser(repo_path, result_dir)
        run_funcid_parser(repo_path, result_dir)
        run_relation_parser(repo_path, result_dir)
        run_extract(repo_path, result_dir)
        
        print(f"Finished processing repo: {repo_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_path}: {e}")

def assign_ports_and_process_repos(dev_eval_path, result_dir, start_port, max_workers, ports_per_repo=4):
    """遍历 DevEval 目录下的每个 repo，并为每个 repo 分配端口进行并行处理"""
    categories = [os.path.join(dev_eval_path, category) for category in os.listdir(dev_eval_path) if os.path.isdir(os.path.join(dev_eval_path, category))]
    
    repo_paths = []
    for category in categories:
        repo_paths += [os.path.join(category, repo) for repo in os.listdir(category) if os.path.isdir(os.path.join(category, repo))]

    # 检查哪些 repo 已经处理过
    repo_to_process = []
    for repo_path in repo_paths:
        repo_name = os.path.basename(repo_path)
        result_repo_dir = os.path.join(result_dir, repo_name)
        if not os.path.exists(result_repo_dir) or not os.path.exists(os.path.join(result_repo_dir, f"{repo_name}.json")):
            repo_to_process.append(repo_path)
        else:
            print(f"Repo {repo_name} already processed, skipping...")

    # 串行处理任务
    for repo_path in repo_to_process:
        # 获取一个空闲的端口
        ports = get_free_port(start_port, ports_per_repo)
        start_port = ports[-1] + 1  # 为下一个 repo 准备端口
        
        # 依次处理每个 repo
        process_repo(repo_path, result_dir, ports)

    print("Finished processing all repos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process repositories in DevEval with parallelism and port assignment.")
    parser.add_argument("dev_eval_path", type=str, help="Path to the DevEval directory.")
    parser.add_argument("result_dir", type=str, help="Directory to store the result outputs.")
    parser.add_argument("--start_port", type=int, default=4001, help="Starting port number for pylsp servers.")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of parallel tasks to run at once.")
    parser.add_argument("--ports_per_repo", type=int, default=4, help="Number of ports to assign to each repo.")
    
    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(args.result_dir, exist_ok=True)

    # 处理所有的 repo，并分配端口
    assign_ports_and_process_repos(args.dev_eval_path, args.result_dir, args.start_port, args.max_workers, args.ports_per_repo)
