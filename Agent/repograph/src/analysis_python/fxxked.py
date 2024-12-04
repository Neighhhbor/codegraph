import os
import subprocess

# 定义 dev_eval_path 路径
dev_eval_path = '/home/shixianjie/codegraph/codegraph/DevEval/Source_Code'  # 请替换成实际路径
result_dir = "./output"

# 获取所有 repo 的路径
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
        
        
# 定义 run.sh 中的命令，接受一个 repo 路径作为参数
def run_scripts(repo_path):
    ports = [3000, 3001, 3002, 3003]
    
    # 1. 执行 repo_parser.py
    subprocess.run(["python", "repo_parser.py", repo_path, "--output_dir", result_dir], check=True)
    
    # 2. 执行 pylsp.py
    subprocess.run(["python", "pylsp.py", repo_path, "--output_dir", result_dir, "--ports"]+ list(map(str, ports)), check=True)
    
    # 3. 执行 defid_parser.py
    subprocess.run(["python", "defid_parser.py", repo_path, "--output_dir", result_dir], check=True)
    
    # 4. 执行 funcid.py
    subprocess.run(["python", "funcid.py", repo_path, "--output_dir", result_dir], check=True)
    
    # 5. 执行 relation_parser.py
    subprocess.run(["python", "relation_parser.py", repo_path, "--output_dir", result_dir], check=True)
    
    # 6. 执行 extract.py
    subprocess.run(["python", "extract.py", repo_path, "--output_dir", result_dir], check=True)

# 遍历所有 repo，执行上述命令

for repo_path in repo_to_process:
    print(f"Processing repository: {repo_path}")
    run_scripts(repo_path)

print("All repositories processed.")
