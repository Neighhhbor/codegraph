import os
import logging
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

class LspClientWrapper:
    _instance = None  # 单例模式实现

    def __new__(cls, project_root):
        if cls._instance is None:
            cls._instance = super(LspClientWrapper, cls).__new__(cls)
            cls._instance.initialize_server(project_root)
        return cls._instance

    def initialize_server(self, project_root):
        """初始化并启动 LSP 服务器，只在首次调用时运行"""
        self.project_root = os.path.abspath(project_root)
        self.config = MultilspyConfig.from_dict({"code_language": "python"})  # 配置语言
        self.logger = MultilspyLogger()
        self.slsp = SyncLanguageServer.create(self.config, self.logger, self.project_root)
        self.active = False  # 标记 LSP 服务器是否活跃

    def start_server(self):
        """启动同步的 LSP 服务器，只启动一次"""
        if not self.active:
            self.server_context = self.slsp.start_server()  # 获取上下文管理器
            self.server_context.__enter__()  # 手动进入上下文管理器
            self.active = True
            logging.info("LSP server started")

    def stop_server(self):
        """停止同步的 LSP 服务器"""
        if self.active:
            self.server_context.__exit__(None, None, None)  # 退出上下文管理器
            self.active = False
            logging.info("LSP server stopped")

    def find_definition(self, file_path, line, character):
        """同步接口，查找定义"""
        if not self.active:
            try:
                self.start_server()
            except Exception as e:
                logging.error(f"Failed to start LSP server: {e}")
                raise RuntimeError("LSP server not started or stopped")

        abs_file_path = os.path.abspath(file_path)
        logging.debug(f"Finding definition in file: {abs_file_path} at line: {line}, character: {character}")

        try:
            # 请求 LSP 查找定义
            result = self.slsp.request_definition(abs_file_path, line, character)
            if not result:
                logging.warning(f"No definition found for {abs_file_path} at line {line}, character {character}")
                return None  # 返回 None 以表示未找到定义
            return result
        except AssertionError as ae:
            logging.error(f"LSP request failed with assertion error: {ae}")
            return None  # 返回 None 表示解析失败
        except Exception as e:
            logging.error(f"Error finding definition for {abs_file_path} at line {line}, character {character}: {e}")
            return None  # 捕获其他异常并返回 None

    def __enter__(self):
        """支持上下文管理器，进入时启动服务器"""
        self.start_server()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器时，停止服务器"""
        self.stop_server()

    def __del__(self):
        """对象销毁时确保资源被释放"""
        self.stop_server()
