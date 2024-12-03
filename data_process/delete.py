import os

def delete_files_in_subdirectories(root_dir, target_filename):
    # 遍历根目录下的所有文件夹和文件
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):  # topdown=False 确保从子目录开始遍历
        # 如果当前目录下有目标文件，删除它
        for filename in filenames:
            if filename == target_filename:
                file_path = os.path.join(dirpath, filename)
                try:
                    os.remove(file_path)
                    print(f"已删除: {file_path}")
                except Exception as e:
                    print(f"删除失败: {file_path}，错误信息: {e}")
        
        # 删除空目录
        try:
            # 仅在当前目录下没有子目录且没有文件时，删除该目录
            if not os.listdir(dirpath):  # 检查目录是否为空
                os.rmdir(dirpath)
                print(f"已删除空目录: {dirpath}")
        except Exception as e:
            print(f"删除空目录失败: {dirpath}，错误信息: {e}")

if __name__ == "__main__":
    # 指定根目录和目标文件名
    root_directory = "/home/shixianjie/codegraph/codegraph/data_process/repograph"  # 修改为你的目标目录
    target_file_name = "repoparser.json"    # 修改为你要删除的文件名

    delete_files_in_subdirectories(root_directory, target_file_name)
