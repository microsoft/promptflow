# Readme Workflow Generator

These tools is used to generate workflows from README.md and python notebook files in the [examples](../../examples/) folder.
* Generated workflows will be placed in [.github/workflows/samples_*](../../.github/workflows/) folder.
* The script will also generate a new explanation [README.md](../../examples/README.md) for all the examples.

## 1. Install dependencies

```bash
pip install -r ../../examples/requirements.txt
pip install -r ../../examples/dev_requirements.txt
```

## 2. Generate workflows

### (Option 1) One Step Generation

At the **root** of the repository, run the following command:

```bash
python scripts/readme/readme.py
```

### (Option 2) Step by Step Generation

At the **root** of the repository, run the following command:

```bash
# Generate workflow from README.md inside examples folder
python scripts/readme/readme_generator.py -g "examples/**/*.ipynb"

# Generate workflow from python notebook inside examples folder
python scripts/readme/workflow_generator.py -g "examples/flows/**/README.md"
```

Multiple inputs are supported.

## 3. Options to control generations of examples [README.md](../../examples/README.md)

### 3.1 Notebook Workflow Generation

* Each workflow contains metadata area, set `.metadata.description` area will display this message in the corresponding cell in [README.md](../../examples/README.md) file.
* When set `.metadata.no_readme_generation` to value `true`, the script will stop generating for this notebook.

### 3.2 README.md Workflow Generation

* For README.md files, only `bash` cells will be collected and converted to workflow. No cells will produce no workflow.
* Readme descriptions are simply collected from the first sentence in the README.md file just below the title. The script will collect words before the first **.** of the fist paragraph. Multi-line sentence is also supported
  * A supported description sentence: `This is a sample workflow for testing.`
  * A not supported description sentence: `Please check www.microsoft.com for more details.`
