# FAQ

This article addresses frequent questions about tool usage.

## VectorDB/Faiss Index/Vector Index Lookup tool rename reminder

When you update flows to code first experience, if the flow utilized the 3 tools (Faiss Index Lookup, Vector Index Lookup, Vector DB Lookup), you may encounter the error message like the below:

<code><i>Package tool 'embeddingstore.tool.faiss_index_lookup.search' is not found in the current environment.</i></code>

To resolve the issue, you have two options:

- **Option 1**
  - Update your runtime to latest version. 
  - Click on "Raw file mode" to switch to the raw code view, then open the "flow.dag.yaml" file.
     ![img](../../media/tool/faq/switch_to_raw_file_mode.png)
  - Update the tool names.
     ![img](../../media/tool/faq/update_tool_name.png)
     
      | Tool | New tool name |
      | ---- | ---- |
      | Faiss Index Lookup tool | promptflow_vectordb.tool.faiss_index_lookup.FaissIndexLookup.search |
      | Vector Index Lookup | promptflow_vectordb.tool.vector_index_lookup.VectorIndexLookup.search |
      | Vector DB Lookup | promptflow_vectordb.tool.vector_db_lookup.VectorDBLookup.search |

  - Save the "flow.dag.yaml"

- **Option 2**
  - Update your runtime to latest version.
  - Remove the old tool and re-create a new tool.