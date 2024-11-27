import os
import subprocess
import argparse
import multiprocessing
import socket
import time

def is_port_available(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex(('127.0.0.1', port))
        return result != 0  # 如果返回 0，表示端口被占用；返回非 0，表示端口可用

def get_free_port(start_port):
    """获取一个空闲的端口"""
    port = start_port
    while not is_port_available(port):
        port += 1  # 如果当前端口被占用，则尝试下一个端口
    return port

def run_repo_parser(repo_path, result_dir):
    """运行 repo_parser.py 脚本"""
    print(f"Running repo_parser.py for {repo_path}")
    cmd = [
        "python", "repo_parser.py", repo_path, "--output_dir", result_dir
    ]
    subprocess.run(cmd, check=True)

def run_pylsp(repo_path, result_dir, port):
    """运行 pylsp.py 脚本"""
    print(f"Running pylsp.py for {repo_path} on port {port}")
    cmd = [
        "python", "pylsp.py", repo_path, "--output_dir", result_dir, "--port", str(port)
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

def process_repo(repo_path, result_dir, port):
    """处理一个repo，按顺序运行多个脚本"""
    try:
        print(f"Starting processing repo: {repo_path} on port {port}")
        
        # 依次运行脚本
        run_repo_parser(repo_path, result_dir)
        run_pylsp(repo_path, result_dir, port)
        run_defid_parser(repo_path, result_dir)
        run_funcid_parser(repo_path, result_dir)
        run_relation_parser(repo_path, result_dir)
        run_extract(repo_path, result_dir)
        
        print(f"Finished processing repo: {repo_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_path}: {e}")

def assign_ports_and_process_repos(dev_eval_path, result_dir, start_port, max_workers):
    """遍历 DevEval 目录下的每个 repo，并为每个 repo 分配端口进行并行处理"""
    # 获取所有类别目录
    categories = [os.path.join(dev_eval_path, category) for category in os.listdir(dev_eval_path) if os.path.isdir(os.path.join(dev_eval_path, category))]
    
    # 初始化信号量，控制最大并发数
    semaphore = multiprocessing.Semaphore(max_workers)

    repo_paths = []
    for category in categories:
        repo_paths += [os.path.join(category, repo) for repo in os.listdir(category) if os.path.isdir(os.path.join(category, repo))]

    # 用进程池处理所有 repo，并分配端口
    with multiprocessing.Pool(processes=max_workers) as pool:
        for repo_path in repo_paths:
            # 获取一个空闲的端口
            port = get_free_port(start_port)
            start_port = port + 1  # 为下一个 repo 准备端口

            # 使用池中的进程执行 repo 处理
            pool.apply_async(process_repo, (repo_path, result_dir, port))

        # 等待所有任务完成
        pool.close()
        pool.join()

    print("Finished processing all repos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process repositories in DevEval with parallelism and port assignment.")
    parser.add_argument("dev_eval_path", type=str, help="Path to the DevEval directory.")
    parser.add_argument("result_dir", type=str, help="Directory to store the result outputs.")
    parser.add_argument("--start_port", type=int, default=3000, help="Starting port number for pylsp servers.")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of parallel tasks to run at once.")
    
    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(args.result_dir, exist_ok=True)

    # 处理所有的 repo，并分配端口
    assign_ports_and_process_repos(args.dev_eval_path, args.result_dir, args.start_port, args.max_workers)
