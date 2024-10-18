import numpy as np
from ..module_b import b
from ..utils.helper import helper_function
from ..module_b.submodule import advanced_function
from typing import Any

def function_a():
    print("这是函数A")
    b.function_b()
    helper_function()
    advanced_function()
    print("使用numpy:", np.array([1, 2, 3]))

def generic_function(x: Any) -> Any:
    return x