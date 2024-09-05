import os
import logging
import asyncio
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from multilspy.language_server import LanguageServer

class LspClientWrapper:
    _instance = None  # 用于确保单例

    def __new__(cls, project_root):
        if cls._instance is None:
            cls._instance = super(LspClientWrapper, cls).__new__(cls)
            cls._instance.project_root = os.path.abspath(project_root)
            cls._instance.config = MultilspyConfig.from_dict({"code_language": "python"})
            cls._instance.logger = MultilspyLogger()
            cls._instance.lsp_server = None
            cls._instance._initialize_server()  # 在构造时初始化 LSP 服务器
        return cls._instance

    def _initialize_server(self):
        """
        启动 LSP 服务器，只执行一次初始化操作
        """
        self.logger.log(f"Starting LSP Server for project: {self.project_root}", logging.INFO)
        # 使用 asyncio.run() 启动异步任务
        asyncio.run(self._start_lsp_server())

    async def _start_lsp_server(self):
        self.lsp_server = await LanguageServer.create(self.config, self.logger, self.project_root)
        self.logger.log(f"LSP Server started for project: {self.project_root}", logging.INFO)

    def stop(self):
        """
        停止 LSP 服务器，同步调用
        """
        if self.lsp_server:
            self.logger.log(f"Stopping LSP Server for project: {self.project_root}", logging.INFO)
            asyncio.run(self._stop_lsp_server())

    async def _stop_lsp_server(self):
        if self.lsp_server:
            await self.lsp_server.server.stop()
            self.logger.log(f"LSP Server stopped for project: {self.project_root}", logging.INFO)

    def find_definition(self, file_path, line, character):
        """
        同步调用 LSP 服务器的 find_definition 方法，返回定义位置
        """
        if not self.lsp_server:
            raise RuntimeError("LSP server not started")

        relative_path = os.path.relpath(file_path, self.project_root)
        # 使用 asyncio.run() 来执行异步的 find_definition 方法，并以同步方式返回结果
        result = asyncio.run(self._find_definition(relative_path, line, character))

        if result:
            self.logger.log(f"Definition found at: {result}", logging.DEBUG)
            return result
        else:
            self.logger.log(f"No definition found for {file_path} at line {line}, character {character}", logging.WARNING)
            return None

    async def _find_definition(self, relative_path, line, character):
        """
        异步调用 LSP 服务器的 find_definition 方法
        """
        return await self.lsp_server.request_definition(relative_path, line, character)

