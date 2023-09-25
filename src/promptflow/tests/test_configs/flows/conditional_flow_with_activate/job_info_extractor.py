from promptflow import tool


@tool
def extract_job_info(incident_content: str) -> str:
    print(f"Incident: {incident_content}")
    return "Execute job info extractor"
