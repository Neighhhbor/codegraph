import os
from module_a import a
from module_b import b
from utils.helper import helper_function

def main():
    print("这是主函数")
    a.function_a()
    b.function_b()
    helper_function()

if __name__ == "__main__":
    main()
