from model_server import start_model_server, stop_model_server
import time

if __name__ == "__main__":
    start_model_server()
    print("模型服务已启动，按 Ctrl+C 停止服务")
    try:
        # 保持进程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在停止模型服务...")
        stop_model_server()
        print("模型服务已停止")
