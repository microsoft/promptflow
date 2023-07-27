def write_workflows(notebooks):
    print("writing .github/workflows...")
    cfg = ConfigParser()
    cfg.read(os.path.join("notebooks_config.ini"))
    for notebook in notebooks:
        notebook_path = notebook.replace(os.sep, "/")
        if not any(excluded in notebook_path for excluded in NOT_TESTED_NOTEBOOKS):
            # get notebook name
            name = os.path.basename(notebook).replace(".ipynb", "")
            folder = os.path.dirname(notebook)
            classification = folder.replace(os.sep, "-")

            enable_scheduled_runs = True
            if any(excluded in notebook_path for excluded in NOT_SCHEDULED_NOTEBOOKS):
                enable_scheduled_runs = False

            # write workflow file
            write_notebook_workflow(
                notebook, name, classification, folder, enable_scheduled_runs, cfg
            )
    print("finished writing .github/workflows")

if __name__ == "__main__":
    pass