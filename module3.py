
import numpy
import numpy as np
from matplotlib import pyplot as plt

class MyClass():
    def __init__(self):
        self.my_var = 10    
    def my_function(self):
        print("MyClass() Hello, World!")
    
    def another_function(self):
        print(numpy.array([1, 2, 3]))
        
    class InnerClass():
        def __init__(self):
            print("This is InnerClass")

class MyOtherClass():
    pass
    
print(np.array([1, 2, 3]))