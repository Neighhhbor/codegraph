import os
import subprocess

def run_script(script_name, repo_path, result_dir, ports=None):
    """运行指定的脚本，传递参数"""
    cmd = ["python", script_name, repo_path, "--output_dir", result_dir]
    if ports:
        cmd.extend(["--ports"] + list(map(str, ports)))  # 添加端口参数
    subprocess.run(cmd, check=True)

def process_repo(repo_path, result_dir, ports):
    """按顺序运行多个脚本处理一个repo"""
    try:
        repo_name = os.path.basename(repo_path)
        
        # 如果输出目录已存在且有输出文件，则跳过
        result_repo_dir = os.path.join(result_dir, repo_name)
        output_file = os.path.join(result_repo_dir, f"{repo_name}.json")
        if os.path.exists(result_repo_dir) and os.path.exists(output_file):
            print(f"Repo {repo_name} already processed, skipping...")
            return
        
        print(f"Processing repo: {repo_path}")
        
        # 依次运行各个脚本
        run_script("repo_parser.py", repo_path, result_dir)
        print("repo_parser.py finished")
        
        run_script("pylsp.py", repo_path, result_dir, ports)
        print("pylsp.py finished")
        
        run_script("defid_parser.py", repo_path, result_dir)
        print("defid_parser.py finished")
        
        # 语言有关部分
        run_script("funcid.py", repo_path, result_dir)
        print("funcid.py finished")
        
        run_script("relation_parser.py", repo_path, result_dir)
        print("relation_parser.py finished")
        
        run_script("extract.py", repo_path, result_dir)
        print("extract.py finished")
        
        print(f"Finished processing repo: {repo_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {repo_path}: {e}")

def process_all_repos(dev_eval_path, result_dir, ports):
    """遍历所有repo并依次处理"""
    categories = [os.path.join(dev_eval_path, category) for category in os.listdir(dev_eval_path) if os.path.isdir(os.path.join(dev_eval_path, category))]
    
    repo_paths = []
    for category in categories:
        repo_paths += [os.path.join(category, repo) for repo in os.listdir(category) if os.path.isdir(os.path.join(category, repo))]

    for repo_path in repo_paths:
        process_repo(repo_path, result_dir, ports)

if __name__ == "__main__":
    dev_eval_path = "/home/shixianjie/codegraph/codegraph/DevEval/Source_Code"
    result_dir = "./output"
    ports = [3000, 3001, 3002, 3003]

    # 确保输出目录存在
    os.makedirs(result_dir, exist_ok=True)

    # 处理所有的repo
    process_all_repos(dev_eval_path, result_dir, ports)
