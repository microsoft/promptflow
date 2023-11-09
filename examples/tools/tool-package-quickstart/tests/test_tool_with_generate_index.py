import json
import unittest

from my_tool_package.tools.tool_with_generate_index import (generate_index_json, list_content_fields, list_embedding_deployment,
                                                            list_indexes, my_tool, reverse_generate_index_json)


def test_my_tool():
    index_type = "MLIndex"
    index = list_indexes(index_type)[0]
    content_field = list_content_fields(index_type)[0]
    embedding_deployment = list_embedding_deployment(index_type)[1]
    index_json = generate_index_json(index_type=index_type, index=index,
                                     content_field=content_field, embedding_deployment=embedding_deployment)
    
    result = my_tool(index_json, index_type, index, content_field, embedding_deployment)
    
    assert result == f'Hello {index_json}'


def test_generate_index_json():
    index_type = "MLIndex"
    index = list_indexes(index_type)[0]
    content_field = list_content_fields(index_type)[0]
    embedding_deployment = list_embedding_deployment(index_type)[1]
    kwargs = {"a": "b", "c": "d"}
    
    index_json = generate_index_json(index_type=index_type, index=index,
                                     content_field=content_field, embedding_deployment=embedding_deployment, **kwargs)
    indexs = json.loads(index_json)

    assert indexs["index_type"] == index_type
    assert indexs["index"] == index
    assert indexs["content_field"] == content_field
    assert indexs["embedding_deployment"] == embedding_deployment
    for k, v in kwargs.items():
        assert indexs[k] == v


def test_list_indexes():
    index_type = "Azure Cognitive Search"
    result = list_indexes(index_type)
    assert len(result) == 2
    assert "1" in result


def test_list_content_fields():
    index_type = "MLIndex"
    result = list_content_fields(index_type)
    assert len(result) == 2
    assert "c" in result


def test_list_embedding_deployment():
    index_type = "MLIndex"
    result = list_embedding_deployment(index_type)
    assert len(result) == 2
    assert "x" in result


def test_reverse_generate_index_json():
    index_type = "MLIndex"
    index = list_indexes(index_type)[0]
    content_field = list_content_fields(index_type)[0]
    embedding_deployment = list_embedding_deployment(index_type)[1]
    indexs = {
        "index_type": index_type,
        "index": index,
        "content_field": content_field,
        "embedding_deployment": embedding_deployment,
    }
    input_json = json.dumps(indexs)
    
    result = reverse_generate_index_json(input_json)
    
    for k, v in indexs.items():
        assert result[k] == v


if __name__ == "__main__":
    unittest.main()
