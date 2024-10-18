from ..utils import helper
import tensorflow as tf
from typing import Callable

def advanced_function():
    print("这是高级函数")
    helper.helper_function()
    print("使用TensorFlow版本:", tf.__version__)

def higher_order_function(func: Callable):
    def wrapper():
        print("开始执行函数")
        func()
        print("函数执行结束")
    return wrapper

@higher_order_function
def decorated_function():
    print("这是被装饰的函数")
