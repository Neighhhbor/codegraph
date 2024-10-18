import datetime
from typing import Union
import sys

def helper_function():
    print("这是辅助函数")
    print("当前时间:", datetime.datetime.now())

def type_check(obj: Union[int, str, list]):
    if isinstance(obj, int):
        print("这是一个整数")
    elif isinstance(obj, str):
        print("这是一个字符串")
    elif isinstance(obj, list):
        print("这是一个列表")

if __name__ == "__main__":
    print("这个模块正在作为脚本运行")
    print("Python版本:", sys.version)