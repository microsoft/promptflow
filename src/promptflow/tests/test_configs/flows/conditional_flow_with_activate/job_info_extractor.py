from promptflow import tool


@tool
def extract_job_info(incident_content: str) -> str:
  return "Job_info: " + incident_content