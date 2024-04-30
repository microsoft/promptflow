import sys
import pathlib

# Add the path to the evaluation module
code_path = str(pathlib.Path(__file__).parent / "../eval-checklist")
sys.path.insert(0, code_path)
