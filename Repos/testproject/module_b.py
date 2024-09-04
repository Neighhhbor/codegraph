from module_a import MyClassA

class MyClassB:
    def method_b(self):
        instance_a = MyClassA()
        return instance_a.method_a()
