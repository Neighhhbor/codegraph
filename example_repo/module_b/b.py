from ..utils.helper import helper_function
import pandas as pd

def function_b():
    print("这是函数B")
    helper_function()
    print("使用pandas:", pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]}))
