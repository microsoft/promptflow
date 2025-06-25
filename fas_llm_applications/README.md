# `fas_llm_applications` - Harvard FAS LLM Applications for Promptflow

This repository contains a collection of PromptFlow-based applications and utilities designed for integrating Large Language Models (LLMs) into Harvard FAS (Faculty of Arts and Sciences) workflows. It provides a structured environment for developing, deploying, and managing LLM-powered solutions, with a focus on secure credential handling and consistent setup.

## Table of Contents

- [`fas_llm_applications` - Harvard FAS LLM Applications for Promptflow](#fas_llm_applications---harvard-fas-llm-applications-for-promptflow)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Project Structure](#project-structure)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Local Development](#local-development)
    - [GitHub Codespaces](#github-codespaces)
  - [Environment Variables \& Secrets](#environment-variables--secrets)
  - [PromptFlow Connections](#promptflow-connections)
  - [Generated Data \& Reports](#generated-data--reports)
  - [Contributing](#contributing)
  - [License](#license)

## Features

* **Modular PromptFlow Applications:** Organized PromptFlows for various LLM use cases.

* **Centralized Connection Management:** Secure and consistent setup for LLM service connections (e.g., Google Gemini, Azure OpenAI, AWS Bedrock).

* **Dev Container Support:** Pre-configured development environment using `devcontainer.json` for easy onboarding and consistent setups across developers.

* **Secure Credential Handling:** Guidance and mechanisms for managing sensitive API keys and secrets out of version control.

* **LLM Run Reporting:** Tools to generate detailed reports for PromptFlow runs, aiding in monitoring and evaluation.

## Project Structure

This project is organized into modular components to enhance maintainability and clarity.

```
fas_llm_applications/
├── _connections_manager_/             # Python package for managing PromptFlow connections.
│   ├── __init__.py                   # Marks this directory as a Python package.
│   ├── aws_connection_utils.py       # Utilities for managing AWS-specific PromptFlow connections (e.g., Bedrock).
│   ├── client_utils.py               # Utilities related to the PromptFlow Client (PFClient) itself.
│   ├── common_secrets_loader.py      # Handles loading common secrets or environment variables for connection setup.
│   ├── gemini_connection_utils.py    # Utilities for managing Google Gemini-specific PromptFlow connections.
│   ├── keyring_utils.py              # Utilities for interacting with the system's keyring service for credentials.
│   └── setup_all_shared_connections.py # The main orchestration script to set up all shared PromptFlow connections.
├── digital_latin_project/             # Sub-project/application specific to the Digital Latin Project.
│   ├── __init__.py                   # Marks this as a Python package.
│   ├── data/                         # Contains input datasets and files for flows and testing.
│   │   ├── *.jsonl                   # JSONL formatted input data for batch runs.
│   │   ├── *.csv                     # CSV files for variant testing or specific test cases.
│   │   └── *.txt                     # Log or output files from previous test runs.
│   ├── flows/                        # PromptFlow definitions specific to the Digital Latin Project.
│   │   ├── basic_claude_llm_flow/    # Example flow using AWS Claude models.
│   │   │   ├── nodes/                # Python tools/nodes for this specific flow.
│   │   │   │   ├── __init__.py
│   │   │   │   └── aws_llm_invocation.py
│   │   │   ├── dl_prompt_node.jinja2 # Jinja2 template for the prompt used in the flow.
│   │   │   └── flow.dag.yaml         # The core PromptFlow definition file.
│   │   ├── basic_deepseek_llm_flow/  # Example flow using Deepseek models.
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   └── aws_llm_invocation.py
│   │   │   ├── dl_prompt_node.jinja2
│   │   │   └── flow.dag.yaml
│   │   ├── basic_gemini_llm_flow/    # Example flow using Google Gemini models.
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   └── gemini_llm_invocation.py
│   │   │   ├── dl_prompt_node.jinja2
│   │   │   └── flow.dag.yaml
│   │   ├── multi_llm_flow/           # Example of a flow designed to utilize multiple LLMs.
│   │   │   ├── default.flow_test.yaml
│   │   │   ├── dl_prompt_node.jinja2
│   │   │   └── flow.dag.yaml
│   │   ├── multi_llm_parallel_flow/  # Example of a flow designed for parallel LLM execution.
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   └── multi_llm_invocation.py
│   │   │   └── flow.dag.yaml
│   │   └── __init__.py               # Marks 'flows' as a Python package.
│   ├── prepared_reports/             # Generated Markdown manifests for LLM run reports.
│   │   └── *.md
│   ├── prompts/                      # Organized collection of Jinja2 prompt templates.
│   │   ├── system/                   # System prompt templates for various LLM roles.
│   │   │   └── *.jinja2
│   │   └── user/                     # User prompt templates for different interaction styles.
│   │       └── *.jinja2
│   ├── results/                      # Generated JSON reports and other detailed outputs from LLM runs.
│   │   ├── *.json
│   │   └── report_counter.txt        # Helper file for sequential report numbering.
│   ├── scripts/                      # Specific scripts related to the Digital Latin Project's operations.
│   │   ├── generate_prepared_reports.py # Script to generate final Markdown reports from run data.
│   │   ├── generate_report.py        # Core script for generating individual LLM reports.
│   │   └── load_env_to_shell.py      # Helper script for loading environment variables (if needed outside dev container).
│   ├── tests/                        # Tests specific to the Digital Latin Project.
│   │   └── .gitkeep                  # Placeholder to ensure the empty directory is tracked by Git.
│   ├── tools/                        # Custom PromptFlow tools developed for this project.
│   │   └── prompt_selector_tool.py
│   ├── utilities/                    # General utility modules for the Digital Latin Project.
│   │   ├── __init__.py
│   │   └── prompt_registry_util.py
│   └── __init__.py                   # Marks 'digital_latin_project' as a Python package.
├── __init__.py                       # Marks 'fas_llm_apps' as a Python package, allowing internal imports.
├── .devcontainer/                    # VS Code Dev Container configuration for a consistent development environment.
│   ├── devcontainer.json             # Main Dev Container definition (installs dependencies, sets up environment).
│   └── devcontainer.json.template    # Template for sensitive variable handling within the dev container.
├── scripts/                          # General utility and execution scripts for the entire `fas_llm_apps` project.
│   ├── run_flow_example.py           # Example script to run a generic PromptFlow (if applicable).
│   └── ...
├── tests/                            # Top-level unit and integration tests for the entire `fas_llm_apps` project.
│   └── .gitkeep                      # Placeholder to ensure the empty directory is tracked by Git.
├── .env.example                      # Template for required environment variables (copy to .env for local use).
├── .gitignore                        # Specifies files to be ignored by Git (e.g., temporary files, secrets).
├── README.md                         # This file, providing an overview and guide for the `fas_llm_apps` project.
├── requirements.txt                  # Python package dependencies for the project.
└── ...
```

## Getting Started

### Prerequisites

* **Git:** For cloning the repository.

* **Docker Desktop:** Required for local Dev Container development.

* **VS Code:** With the "Dev Containers" extension installed.

* **LLM Service Access:** Depending on the LLMs you integrate (e.g., Google Gemini API Key, Azure Machine Learning Workspace, Azure OpenAI deployment, AWS credentials for Bedrock).


### Local Development

This project's VS Code Dev Container configuration is designed to align with the development environment of the PromptFlow repository, ensuring consistency with PromptFlow best practices.

1.  **Ensure Docker is Running:**
    Before starting, make sure your Docker Desktop application (or Docker daemon) is running on your machine. The Dev Container relies on Docker to build and run its containerized environment.

2.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-org/fas_llm_apps.git](https://github.com/your-org/fas_llm_apps.git)
    cd fas_llm_apps
    ```

3.  **Create `.env` file for Local Variables:**
    Copy the `.env.example` file to `.env` in the root of your `fas_llm_apps` directory. Fill in your actual, non-sensitive configuration values. **Ensure `.env` is listed in your `.gitignore` and never committed, as it may contain sensitive information.**
    ```bash
    cp .env.example .env
    # Open .env and fill in your values
    ```

4.  **Opening the Project in its Dev Container:**

    To ensure you are working within the dedicated Dev Container for *this* `fas_llm_apps` project (and not a parent repository's Dev Container), follow these specific steps:

    a.  **Close Current VS Code Window (if open on the parent `promptflow` repo):**
        If your VS Code is currently open to the higher-level `promptflow/` directory, close that VS Code window first (`File > Close Folder` or `File > Close Window`).

    b.  **Open Only the `fas_llm_apps` Folder in VS Code:**
        * Launch VS Code.
        * Go to **File > Open Folder...** (or **Code > Open Folder...** on macOS).
        * **Navigate to and select specifically the `fas_llm_applications` directory.** This is crucial. Your VS Code workspace's root must be `fas_llm_applications/`, not the parent `promptflow/` directory.
        * Click "Open".

    c.  **Reopen in Container (Automatic Prompt):**
        * After opening the `fas_llm_applications` folder, VS Code should detect its `.devcontainer` configuration. You will likely see a notification pop up in the bottom-right corner (or a small green remote indicator in the bottom-left status bar) asking: **"Folder contains a Dev Container configuration. Reopen in Container?"**
        * Click on **"Reopen in Container"** in that notification.

    d.  **Reopen in Container (Manual Trigger if Prompt is Missed):**
        * If you don't see the automatic prompt for any reason, click the **green remote indicator** in the bottom-left corner of the VS Code status bar (it looks like `<>`).
        * From the command palette that appears at the top, select **"Reopen in Container"** (or **"Open Folder in Container..."** if it's the very first time you're attempting this for the folder and it's not prompting automatically). Then, select the `fas_llm_applications` folder again.

    e.  **Container Build Process:**
        VS Code will then proceed to build (if necessary) and launch your `fas_llm_apps` Dev Container. This initial setup might take a few minutes. You can monitor the progress in the VS Code status bar.

    f.  **Ready to Develop:**
        Once the process completes, your VS Code window will reload, and you'll be connected to the Dev Container specific to `fas_llm_apps`. The green remote indicator will confirm you are "Dev Container: [Your Container Name]". You can open the integrated terminal (`Ctrl+\` or `Cmd+\``) and verify your environment.

5.  **Initialize PromptFlow Connections:**
    Your `setup_all_shared_connections.py` script (located in `_connections_manager_`) will be executed automatically during Dev Container startup (via `postCreateCommand`) or can be run manually to ensure your PromptFlow connections are correctly set up based on your environment variables.

    ```bash
    # This might be run automatically during devcontainer startup.
    # Otherwise, you can run it manually in the terminal:
    python -m fas_llm_apps._connections_manager_.setup_all_shared_connections
    ```

### GitHub Codespaces

GitHub Codespaces provides a ready-to-use cloud development environment pre-configured for this project:

1.  **Open in Codespaces:**

    * Navigate to your repository on GitHub.

    * Click on the green "Code" button and select the "Codespaces" tab.

    * Choose to create a new codespace for the `fas_llm_apps` directory.

2.  **Define Secrets:**
    For **sensitive variables** (e.g., API keys, service principals), define them as **repository secrets** in GitHub. These are securely injected into your Codespace environment.

    * Go to `Repository Settings > Secrets and variables > Codespaces`.

    * Add new repository secrets corresponding to the variable names listed in `.env.example` (e.g., `AZURE_SUBSCRIPTION_ID`, `GOOGLE_GEMINI_API_KEY`, `AWS_ACCESS_KEY_ID`).

3.  **Environment Setup:**
    Codespaces will automatically:

    * Load secrets defined in your GitHub repository into the Codespace environment.

    * Install Python dependencies from `requirements.txt`.

    * Your PromptFlow connections will be set up automatically based on these environment variables during the Codespace startup.

## Environment Variables & Secrets

This project relies on several environment variables for configuration and credentials. Refer to `.env.example` for a complete list of required environment variables.

* **For Local Development:** Copy `.env.example` to `.env` in the root of `fas_llm_apps/` and fill in your values. This `.env` file should **NOT** be committed to Git.

* **For GitHub Codespaces:**

  * **Sensitive variables:** Define these as **repository secrets** under `Repository Settings > Secrets and variables > Codespaces`.

  * **Other variables:** You can still use a `.env` file in the Codespace workspace root (copied from `.env.example`) to automatically load non-sensitive variables into your Codespace environment.

## PromptFlow Connections

PromptFlow requires connections to various LLM services (e.g., Azure OpenAI, AWS Bedrock, Google Gemini). This project centralizes connection management through the `_connections_manager_` package:

* It handles the initialization of the `PFClient` and ensures the existence and correct configuration of all necessary PromptFlow connections.

* Connections are configured using environment variables, securely pulling credentials.

* The `setup_all_shared_connections.py` script verifies your `keyring` setup and creates/updates PromptFlow connections as needed. This script is designed to run automatically during development environment setup.

## Generated Data & Reports

During development and testing, this project generates various data files and reports, which are currently **tracked within the repository** for ease of understanding and analysis during the learning phase.

* **`digital_latin_project/data/`**: Contains various input data files used for batch runs and testing.

* **`digital_latin_project/results/`**: Stores detailed JSON reports and other raw outputs from PromptFlow runs.

* **`digital_latin_project/prepared_reports/`**: Contains human-readable Markdown manifest files for generated LLM run reports.

* **Log and Text Files**: All `.log` and `.txt` files generated by PromptFlow flows or scripts are currently included to aid in debugging and understanding flow behavior.

As the project matures, these generated files may be moved to a dedicated data store or excluded from version control via `.gitignore` updates.

## Contributing

Contributions are welcome! Please refer to `CONTRIBUTING.md` (if it exists) for guidelines on how to contribute.

## License

TBD.
