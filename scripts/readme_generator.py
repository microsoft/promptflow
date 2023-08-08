from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from ghactions_driver.readme_step import ReadmeStepsManage, ReadmeSteps


def main():
    template_folder = (
        Path(ReadmeStepsManage.git_base_dir())
        / "scripts"
        / "ghactions_driver"
        / "readme_templates"
    )

    jinja_env = Environment(loader=FileSystemLoader(template_folder))
    template_names = jinja_env.list_templates()
    # get list of workflows
    values = {"Steps": ReadmeSteps}

    for template_name in template_names:
        workflow_name = template_name.split(".")[0]
        pipeline_name = "auto_generated_steps"
        template = jinja_env.get_template(template_name)
        content = template.render(values)  # side effect: ReadmeSteps is changed
        ReadmeStepsManage.write_readme(content)
        ReadmeStepsManage.write_workflow(workflow_name, pipeline_name)
        ReadmeSteps.cleanup()


if __name__ == "__main__":
    main()
