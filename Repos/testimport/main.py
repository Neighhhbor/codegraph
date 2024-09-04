# 第三方库导入
import os
import sys
import requests  # 假设是安装的第三方库
from datetime import datetime

# 项目内导入
from utils.helper import greet
from utils.formatter import format_text
from external.third_party import external_function

def main():
    name = "World"
    # 使用项目内导入的函数
    greeting = greet(name)
    formatted_greeting = format_text(greeting)
    
    # 打印第三方库信息
    print(f"Operating System: {os.name}")
    print(f"Current time: {datetime.now()}")
    
    # 假设发送 HTTP 请求
    response = requests.get("https://example.com")
    print(f"Request status code: {response.status_code}")
    
    # 使用项目内其他模块函数
    external_function(formatted_greeting)

if __name__ == "__main__":
    main()
