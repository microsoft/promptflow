from promptflow import tool
from dependency_folder.dependency import say_hello


@tool
def build_vector_index():
    print("test" + say_hello())
