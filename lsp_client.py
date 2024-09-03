from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
import os
import logging
import time

class LspClientWrapper:
    def __init__(self, project_root):
        self.project_root = os.path.abspath(project_root)  # 转换为绝对路径
        self.config = MultilspyConfig.from_dict({"code_language": "python"})
        self.logger = MultilspyLogger()
        self.slsp = SyncLanguageServer.create(self.config, self.logger, self.project_root)

    def find_definition(self, file_path, line, character, max_retries=1, delay=1.0):
        """
        通过LSP查找定义，加入重试和延迟机制，并处理可能的异常。

        参数:
            file_path (str): 源文件的路径。
            line (int): 请求定义的行号。
            character (int): 请求定义的列号。
            max_retries (int): 最大重试次数。
            delay (float): 每次重试之间的延迟时间（秒）。

        返回:
            LSP响应的定义位置，如果失败则返回None。
        """
        logging.debug(f"Starting LSP server for project: {self.project_root}")
        abs_file_path = os.path.abspath(file_path)  # 确保文件路径是绝对路径

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            try:
                with self.slsp.start_server():
                    logging.debug(f"Attempt {attempt}: Finding definition in file: {abs_file_path} at line: {line}, character: {character}")
                    result = self.slsp.request_definition(abs_file_path, line, character)
                    if result:
                        logging.debug(f"Definition found: {result}")
                        return result
                    else:
                        logging.warning(f"Attempt {attempt}: No definition found for {abs_file_path} at line: {line}, character: {character}. Retrying...")
            except AssertionError as e:
                logging.error(f"Attempt {attempt}: LSP request failed for {abs_file_path} at line: {line}, character: {character}: {e}")
            except Exception as ex:
                logging.error(f"Attempt {attempt}: Unexpected error: {ex}")
            
            time.sleep(delay)
        
        logging.error(f"Failed to find definition after {max_retries} attempts.")
        return None
