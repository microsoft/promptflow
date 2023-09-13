from promptflow import tool


@tool
def extract_incident_info(incident: dict) -> str:
  retriever_type = ["icm", "tsg", "kql"]
  return {
    "retriever": retriever_type[incident["incident_id"]],
    "incident_content": incident["incident_content"]
  }