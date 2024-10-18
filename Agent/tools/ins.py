import inspect

def example(a, b=42, *args, **kwargs):
    pass

sig = inspect.signature(example)
print(sig)  # 输出：(a, b=42, *args, **kwargs)


def foo():
    return 42

print(inspect.getsource(foo))
# 输出:
# def foo():
#     return 42
import os
print(inspect.getfile(os))  # 输出 os 模块定义的文件路径
