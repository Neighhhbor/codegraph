from module_c.submodule_b import utility_function

class MyClassA:
    def method_a(self):
        return "Method A"

    @staticmethod
    def static_method_a():
        print("Static Method A")

    def outer_method(self):
        def inner_method():
            return "Inner Method"
        return inner_method()

    def call_utility_function(self):
        return utility_function()
