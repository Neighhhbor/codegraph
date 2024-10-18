import datetime
from typing import Union
import sys
import time
from functools import wraps

def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} 执行时间: {end_time - start_time:.4f} 秒")
        return result
    return wrapper

@timing_decorator
def helper_function():
    print("这是辅助函数")
    print("当前时间:", datetime.datetime.now())

@timing_decorator
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
    type_check(42)
    type_check("Hello")
    type_check([1, 2, 3])
