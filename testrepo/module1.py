# module1.py
class MyClass:
    def outer_method(self):
        def inner_function():
            pass
        inner_function()
        a = inner_function
        a()

def standalone_function():
    pass