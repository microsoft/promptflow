import os
from pathlib import Path

saved_path = os.getcwd()
os.chdir(Path(__file__).parent)

source_folder = Path("../web-classification")
for file_name in os.listdir(source_folder):
    if not Path(file_name).exists():
        os.symlink(
            source_folder / file_name,
            file_name
        )

os.chdir(saved_path)
