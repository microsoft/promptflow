# `digital_latin_project` - LLM Applications for Digital Latin Analysis

This directory (`digital_latin_project/`) houses the PromptFlow-based applications specifically tailored for the Digital Latin Project within the broader `fas_llm_applications` directory. Its primary goal is to leverage Large Language Models (LLMs) for various tasks related to the analysis, understanding, and generation of scaffolded Latin text, facilitating teaching and learning in the humanities.

## Table of Contents

* [Context within `fas_llm_apps`](#context-within-fas_llm_apps)

* [Components](#components)

  * [Data (`data/`)](#data-data)

  * [Flows (`flows/`)](#flows-flows)

  * [Prompts (`prompts/`)](#prompts-prompts)

  * [Scripts (`scripts/`)](#scripts-scripts)

  * [Tools (`tools/`)](#tools-tools)

  * [Utilities (`utilities/`)](#utilities-utilities)

  * [Results & Reports (`results/`, `prepared_reports/`)](#results--reports-results-prepared_reports)

* [Usage](#usage)

  * [Running Flows](#running-flows)

  * [Generating Reports](#generating-reports)

## Context within `fas_llm_apps`

The `digital_latin_project` is a key sub-project of `fas_llm_applications`. While `fas_llm_applications` provides the foundational infrastructure (like connection management and the overall development environment), this directory contains the domain-specific logic, data, and PromptFlow definitions pertinent to Latin text analysis.

For setting up the development environment (Dev Container, Codespaces) and managing LLM connections, please refer to the main [`fas_llm_applications/README.md`](../README.md) document.

## Components

### Data (`data/`)

This folder contains the datasets and input files used by the PromptFlows and scripts within the `digital_latin_project`.

* `*.jsonl`: JSON Lines files, often used for batch processing with PromptFlow, where each line is a separate input record.

* `*.csv`: CSV files, typically used for variant testing, specific test cases, or structured input data.

* `*.txt`: Various text files, which may include raw texts, logs from previous runs, or other unstructured data.

### Flows (`flows/`)

This directory contains the PromptFlow definitions (`flow.dag.yaml`) and their associated Python nodes and prompt templates. Each subdirectory represents a distinct PromptFlow designed for a specific task.

* **`basic_claude_llm_flow/`**: An example PromptFlow demonstrating interaction with AWS Claude models, including its custom Python invocation node and Jinja2 prompt template.

* **`basic_deepseek_llm_flow/`**: Similar to the Claude flow, but configured to use Deepseek models.

* **`basic_gemini_llm_flow/`**: An example PromptFlow demonstrating interaction with Google Gemini models, with its specific Python invocation node and Jinja2 prompt template.

* **`multi_llm_flow/`**: A more advanced flow showcasing how to integrate and potentially orchestrate calls to multiple LLMs within a single PromptFlow.

* **`multi_llm_parallel_flow/`**: Demonstrates the execution of LLM calls in parallel within a PromptFlow, utilizing a custom multi-LLM invocation node.

* **`flow.dag.yaml`**: The core YAML definition file for each PromptFlow, describing its nodes, inputs, outputs, and connections.

* **`dl_prompt_node.jinja2`**: Jinja2 template files used within the PromptFlows to dynamically construct prompts for LLMs.

### Prompts (`prompts/`)

This structured collection holds Jinja2 template files for various system and user prompts used across the LLM applications. This separation allows for easy iteration and management of prompt engineering.

* **`system/`**: Contains system-level prompt templates that define the LLM's persona, role, or general instructions (e.g., `general_neutral_system.jinja2`, `sophisticated_qa_system.jinja2`).

* **`user/`**: Contains user-facing prompt templates that structure the user's input or questions for the LLMs (e.g., `basic_qa_user.jinja2`, `u1.0_virgil_user.jinja2`).

### Scripts (`scripts/`)

This directory contains Python scripts for specific operations related to the `digital_latin_project`.

* **`generate_prepared_reports.py`**: A script used to process raw LLM run results and generate more polished, human-readable Markdown reports.

* **`generate_report.py`**: A core script that likely handles the detailed logic for creating individual LLM evaluation reports.

* **`load_env_to_shell.py`**: A helper script, primarily for local environments outside of a Dev Container, to load `.env` variables into the shell.

### Tools (`tools/`)

This folder contains custom Python tools that can be integrated as nodes within PromptFlows.

* **`prompt_selector_tool.py`**: A custom tool designed to select or dynamically choose a prompt based on certain input criteria, enhancing prompt engineering flexibility.

### Utilities (`utilities/`)

Contains general utility modules that support the `digital_latin_project`'s functionality.

* **`prompt_registry_util.py`**: A utility for managing and accessing the various prompt templates defined in the `prompts/` directory.

### Results & Reports (`results/`, `prepared_reports/`)

For understanding and debugging during the development phase, all generated run results and reports are currently tracked directly within this repository.

* **`results/`**: Stores the raw JSON outputs and structured data from PromptFlow runs. Each file (e.g., `llm_report_00002.json`) represents the detailed output of a specific LLM interaction or batch run.

* **`prepared_reports/`**: Contains the generated Markdown reports (e.g., `llm_report_00002.md`, `llm_report_smoke_test_2_run_1_test_case_1.md`), which are a more readable summary of the LLM outputs and evaluations. `prepared_report_manifest_*.md` files likely summarize multiple reports.

## Usage

To utilize the PromptFlows within this project, ensure you have followed the setup instructions in the main [`fas_llm_apps/README.md`](../README.md), especially regarding Dev Containers and PromptFlow connection setup.

### Running Flows

Once your development environment is set up and PromptFlow connections are active, you can run individual flows or batch runs.

For example, to test a basic Gemini LLM flow:

```
# Navigate to the fas_llm_apps root
cd /path/to/fas_llm_applications

# Assuming your dev container is running and PromptFlow is installed
# and connections are set up.

# You might use a script or the PromptFlow CLI directly
# Example using pf CLI to test a flow (syntax may vary slightly based on PromptFlow version):
pf flow test --flow digital_latin_project/flows/basic_gemini_llm_flow --inputs your_input_key="Your Latin text here."

# To run a batch test with data from the 'data' folder:
pf flow run create --flow digital_latin_project/flows/basic_claude_llm_flow --data digital_latin_project/data/batch1.jsonl

```

(Refer to PromptFlow documentation for precise CLI commands and options.)

### Generating Reports

After running your PromptFlows, you can use the scripts in `scripts/` to generate reports.

For example, to generate prepared reports from the `results/` directory:

```
# Navigate to the digital_latin_project scripts directory
cd /path/to/fas_llm_apps/digital_latin_project/scripts

# Run the script to generate prepared reports
python generate_prepared_reports.py

```

This will process the JSON results and save Markdown reports in the `prepared_reports/` directory.
