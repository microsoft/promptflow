import pytest
from promptflow.azure._storage.cosmosdb.span import Span
from promptflow._sdk.entities._trace import Span as SpanEntity
from promptflow.azure._storage.cosmosdb.client import get_client_with_workspace_info
import uuid
    
@pytest.mark.e2etest
def test_cosmosdb_insert():
    span_id = str(uuid.uuid1())
    span = Span(
        SpanEntity(
            name="prepare_examples",
            context={
                "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                "span_id": span_id,
                "trace_state": "[]"
            },
            kind="SpanKind.INTERNAL",
            parent_span_id="0x78d79b0696014656",
            start_time="2024-01-31T07:47:07.230106Z",
            end_time="2024-01-31T07:47:07.232107Z",
            status={
                "status_code": "OK"
            },
            attributes={
                "framework": "promptflow",
                "span_type": "promptflow.TraceType.TOOL",
                "function": "prepare_examples",
                "inputs": "{}",
                "node_name": "prepare_examples",
                "tool_version": "tool_version",
                "line_run_id": "7e27a848-476f-42dc-9616-bb7f1054b897",
                "session_id": "7e27a848-476f-42dc-9616-bb7f1054b897",
                "output": "[\n  {\n    \"url\": \"https://play.google.com/store/apps/details?id=com.spotify.music\",\n    \"text_content\": \"Spotify is a free music and podcast streaming app with millions of songs, albums, and original podcasts. It also offers audiobooks, so users can enjoy thousands of stories. It has a variety of features such as creating and sharing music playlists, discovering new music, and listening to popular and exclusive podcasts. It also has a Premium subscription option which allows users to download and listen offline, and access ad-free music. It is available on all devices and has a variety of genres and artists to choose from.\",\n    \"category\": \"App\",\n    \"evidence\": \"Both\"\n  },\n  {\n    \"url\": \"https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw\",\n    \"text_content\": \"NFL Sunday Ticket is a service offered by Google LLC that allows users to watch NFL games on YouTube. It is available in 2023 and is subject to the terms and privacy policy of Google LLC. It is also subject to YouTube's terms of use and any applicable laws.\",\n    \"category\": \"Channel\",\n    \"evidence\": \"URL\"\n  },\n  {\n    \"url\": \"https://arxiv.org/abs/2303.04671\",\n    \"text_content\": \"Visual ChatGPT is a system that enables users to interact with ChatGPT by sending and receiving not only languages but also images, providing complex visual questions or visual editing instructions, and providing feedback and asking for corrected results. It incorporates different Visual Foundation Models and is publicly available. Experiments show that Visual ChatGPT opens the door to investigating the visual roles of ChatGPT with the help of Visual Foundation Models.\",\n    \"category\": \"Academic\",\n    \"evidence\": \"Text content\"\n  },\n  {\n    \"url\": \"https://ab.politiaromana.ro/\",\n    \"text_content\": \"There is no content available for this text.\",\n    \"category\": \"None\",\n    \"evidence\": \"None\"\n  }\n]"
            },
            events=[],
            links=[],
            resource={
                "attributes": {
                    "service.name": "promptflow",
                    "subscription_id": "96aede12-2f73-41cb-b983-6d11a904839b",
                    "resource_group_name": "promptflow",
                    "workspace_name": "promptflow-canary-dev",
                },
                "schema_url": ""
            },
            session_id="7e27a848-476f-42dc-9616-bb7f1054b897",
            span_type=None,
        )
    )

    span_client = get_client_with_workspace_info("Span", {"subscription_id": "96aede12-2f73-41cb-b983-6d11a904839b", "resource_group_name": "promptflow", "workspace_name": "promptflow-canary-dev"})
    data = span.persist(span_client)
    assert data is not None
    assert data.get("id") == span_id

    dup_result = span.persist(span_client)
    assert dup_result is None


