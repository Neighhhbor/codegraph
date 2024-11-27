import os
import json


class RepoWindowProcessor:
    def __init__(self, base_dir, output_dir, window_size, overlap):
        """
        初始化
        :param base_dir: 源代码根目录，例如 "Source_Code/"
        :param output_dir: 窗口化数据的输出目录
        :param window_size: 窗口大小
        :param overlap: 重叠大小
        """
        self.base_dir = base_dir
        self.output_dir = output_dir
        self.window_size = window_size
        self.overlap = overlap

    def _read_file(self, file_path):
        """
        读取单个文件内容
        :param file_path: 文件路径
        :return: 文件内容字符串
        """
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _chunk_code(self, file_path, code, project_root):
        """
        对单个文件的代码进行窗口化
        :param file_path: 文件的绝对路径
        :param code: 文件的代码内容
        :param project_root: 项目根目录，用于生成相对路径
        :return: 窗口化的结果列表
        """
        relative_path = os.path.relpath(file_path, start=project_root.parent)  # 获取相对路径
        
        chunks = []
        lines = code.splitlines()
        step = self.window_size - self.overlap
        for i in range(0, len(lines), step):
            start = i
            end = min(i + self.window_size, len(lines))
            chunk_lines = lines[start:end]
            if chunk_lines:  # 确保非空窗口
                chunks.append({
                    "context": "\n".join(chunk_lines),
                    "metadata": {
                        "file_path": relative_path,  # 保存相对路径
                        "start_line": start,
                        "end_line": end,
                        "window_size": self.window_size,
                        "overlap": self.overlap,
                    },
                })
        return chunks

    def get_repos(self):
        """
        获取所有项目的路径列表
        :return: 项目路径列表
        """
        repo_list = []
        for category in os.listdir(self.base_dir):
            category_path = os.path.join(self.base_dir, category)
            if not os.path.isdir(category_path):  # 跳过非目录
                continue

            for project in os.listdir(category_path):
                project_path = os.path.join(category_path, project)
                if os.path.isdir(project_path):  # 确保是项目目录
                    repo_list.append(project_path)

        return repo_list

    def process_repo(self):
        """
        遍历所有项目，对每个项目的 .py 文件进行窗口化，并单独保存到 JSON 文件
        """
        # 获取所有项目路径
        repos = self.get_repos()

        for repo in repos:
            print(f"Processing repo: {repo}")
            project_chunks = []  # 当前项目的所有窗口化结果

            for root, _, files in os.walk(repo):
                for file in files:
                    if not file.endswith(".py"):  # 仅处理 Python 文件
                        continue
                    file_path = os.path.join(root, file)
                    try:
                        code = self._read_file(file_path)
                        chunks = self._chunk_code(file_path, code, project_root=repo)
                        project_chunks.extend(chunks)
                    except Exception as e:
                        print(f"Error processing file {file_path}: {e}")

            # 将当前项目的结果保存为单独的 JSON 文件
            self._save_project_chunks(repo, project_chunks)

    def _save_project_chunks(self, repo_path, chunks):
        """
        保存当前项目的窗口化结果到一个 JSON 文件
        :param repo_path: 项目路径
        :param chunks: 窗口化结果列表
        """
        # 生成输出文件路径，文件名为项目文件夹名
        project_name = os.path.basename(repo_path)
        output_file = os.path.join(self.output_dir, f"{project_name}_windows.json")

        os.makedirs(self.output_dir, exist_ok=True)  # 确保输出目录存在

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2)

        print(f"Saved {len(chunks)} chunks for project: {project_name} to {output_file}")


# 使用示例
if __name__ == "__main__":
    # 输入根目录和输出目录
    base_dir = "/home/shixianjie/codegraph/codegraph/DevEval/Source_Code"  # 替换为你的根目录路径
    output_dir = "Windowed_Projects"  # 窗口化数据的输出目录

    # 指定窗口大小和重叠大小
    window_size = 100
    overlap = 2

    # 创建处理器并执行
    processor = RepoWindowProcessor(base_dir, output_dir, window_size=window_size, overlap=overlap)
    processor.process_repo()
