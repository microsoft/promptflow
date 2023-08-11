# Generate Readme file for the examples folder
import workflow_generator
import readme_generator

input_glob = ["examples/**/*.ipynb"]
workflow_generator.main(input_glob)

input_glob_readme = ["examples/flows/**/README.md"]
readme_generator.main(input_glob)
