class A:
    def __init__(self, value):
        self.value = value

    def b(self):
        print(f"Called b() with value: {self.value}")
        # 假设 b() 方法处理了一些逻辑，然后返回自身以支持链式调用
        return self

    def c(self):
        print(f"Called c() with value: {self.value}")
        # 假设 c() 方法处理了一些逻辑，然后返回自身以支持链式调用
        return self

    def d(self, increment):
        self.value += increment
        print(f"Called d(), incremented value to: {self.value}")
        # d() 方法返回 self 以支持链式调用
        return self

# 链式调用示例
a = A(10)
a.b().c().d(5).b().d(10)  # 链式调用: b() -> c() -> d(5) -> b() -> d(10)
