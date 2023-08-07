from jinja2 import Environment, FileSystemLoader
from readme_step import ReadmeSteps, ReadmeStepsManage


if __name__ == "__main__":
    # Load templates file from templates folder
    values = {"Steps": ReadmeSteps}
    template = Environment(loader=FileSystemLoader("./readme_templates")).get_template(
        "flow_standard_basic.md.jinja2"
    )
    content = template.render(values)
    ReadmeStepsManage.write_readme(content)
    ReadmeStepsManage.write_workflow()
