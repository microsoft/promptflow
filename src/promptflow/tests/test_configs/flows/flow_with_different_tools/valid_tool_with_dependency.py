from pathlib import Path
from promptflow.core import tool
from dependency_folder.dependency import say_hello

# Customer may want to read other files by relative path as loading tool.
# Add assert for this scenario.
assert Path("dependency_folder", "dependency.py").resolve().absolute().exists()

@tool
def build_vector_index():
    print("test" + say_hello())
