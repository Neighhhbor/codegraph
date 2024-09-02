from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
import os
import logging

class LspClientWrapper:
    def __init__(self, project_root):
        self.project_root = os.path.abspath(project_root)  # 转换为绝对路径
        self.config = MultilspyConfig.from_dict({"code_language": "python"})
        self.logger = MultilspyLogger()
        self.slsp = SyncLanguageServer.create(self.config, self.logger, self.project_root)

    def find_definition(self, file_path, line, character):
        logging.debug(f"Starting LSP server for project: {self.project_root}")
        with self.slsp.start_server():
            abs_file_path = os.path.abspath(file_path)  # 确保文件路径是绝对路径
            logging.debug(f"Finding definition in file: {abs_file_path} at line: {line}, character: {character}")
            return self.slsp.request_definition(abs_file_path, line, character)
