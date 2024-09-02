from module_a import MyClassA
from module_b import MyClassB
from module_c.submodule_a import function_in_submodule_a

def main():
    instance_a = MyClassA()
    instance_b = MyClassB()

    # 调用类的方法
    result_a = instance_a.method_a()
    result_b = instance_b.method_b()

    # 调用静态方法
    MyClassA.static_method_a()

    # 调用嵌套函数
    nested_result = instance_a.outer_method()

    # 调用子模块中的函数
    submodule_result = function_in_submodule_a()

    print(result_a, result_b, nested_result, submodule_result)

if __name__ == "__main__":
    main()
