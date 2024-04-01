import json

import pytest

testdata = """The event sourcing pattern involves using an append-only store to record the full series
of actions on that data. The Azure Cosmos DB change feed is a great choice as a central data store in
event sourcing architectures in which all data ingestion is modeled as writes (no updates or deletes).
In this case, each write to Azure Cosmos DB is an \"event,\" so there's a full record of past events
in the change feed. Typical uses of the events published by the central event store are to maintain materialized
views or to integrate with external systems. Because there's no time limit for retention in the change feed latest
version mode, you can replay all past events by reading from the beginning of your Azure Cosmos DB container's
change feed. You can even have multiple change feed consumers subscribe to the same container's change feed."""


@pytest.mark.skipif(
    condition=not pytest.is_live, reason="serving tests, only run in live mode as replay do not have az login."
)
@pytest.mark.usefixtures("flow_serving_client_remote_connection")
@pytest.mark.e2etest
def test_local_serving_api_with_remote_connection(flow_serving_client_remote_connection):
    response = flow_serving_client_remote_connection.get("/health")
    assert b"Healthy" in response.data
    response = flow_serving_client_remote_connection.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())


@pytest.mark.skipif(condition=not pytest.is_live, reason="serving tests, only run in live mode.")
@pytest.mark.usefixtures("flow_serving_client_with_prt_config_env")
@pytest.mark.e2etest
def test_azureml_serving_api_with_prt_config_env(flow_serving_client_with_prt_config_env):
    response = flow_serving_client_with_prt_config_env.get("/health")
    assert b"Healthy" in response.data
    response = flow_serving_client_with_prt_config_env.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
    response = flow_serving_client_with_prt_config_env.get("/")
    assert b"Welcome to promptflow app" in response.data


@pytest.mark.skipif(condition=not pytest.is_live, reason="serving tests, only run in live mode.")
@pytest.mark.usefixtures("flow_serving_client_with_connection_provider_env")
@pytest.mark.e2etest
def test_azureml_serving_api_with_conn_provider_env(flow_serving_client_with_connection_provider_env):
    response = flow_serving_client_with_connection_provider_env.get("/health")
    assert b"Healthy" in response.data
    response = flow_serving_client_with_connection_provider_env.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
    response = flow_serving_client_with_connection_provider_env.get("/")
    assert b"Welcome to promptflow app" in response.data


@pytest.mark.skipif(condition=not pytest.is_live, reason="serving tests, only run in live mode.")
@pytest.mark.usefixtures("flow_serving_client_with_connection_provider_env")
@pytest.mark.e2etest
def test_azureml_serving_api_with_aml_resource_id_env(flow_serving_client_with_aml_resource_id_env):
    response = flow_serving_client_with_aml_resource_id_env.get("/health")
    assert b"Healthy" in response.data
    response = flow_serving_client_with_aml_resource_id_env.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())


@pytest.mark.skipif(condition=not pytest.is_live, reason="serving tests, only run in live mode.")
@pytest.mark.usefixtures("serving_client_with_connection_name_override")
@pytest.mark.e2etest
def test_azureml_serving_api_with_connection_name_override(serving_client_with_connection_name_override):
    response = serving_client_with_connection_name_override.get("/health")
    assert b"Healthy" in response.data

    response = serving_client_with_connection_name_override.post("/score", data=json.dumps({"text": testdata}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "api_base" not in json.loads(response.data.decode()).values()


@pytest.mark.usefixtures("serving_client_with_connection_data_override")
@pytest.mark.e2etest
def test_azureml_serving_api_with_connection_data_override(serving_client_with_connection_data_override):
    response = serving_client_with_connection_data_override.get("/health")
    assert b"Healthy" in response.data

    response = serving_client_with_connection_data_override.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "api_base" in json.loads(response.data.decode()).values()
