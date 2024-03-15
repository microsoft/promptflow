import sys
import pathlib

# Add the path to the evaluation code quality module
code_path = str(pathlib.Path(__file__).parent / "../eval-code-quality")
sys.path.insert(0, code_path)
