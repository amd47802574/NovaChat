from pymilvus import MilvusClient, DataType, Function, FunctionType

client = MilvusClient(uri="http://localhost:19530", timeout=30)
collection_name = "embeddings_collection"

if client.has_collection(collection_name):
    print("✅ 集合存在")
else:
    print("❌ 集合不存在，正在创建...")

    schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("dense_embedding", DataType.FLOAT_VECTOR, dim=1024)
    schema.add_field("sparse_embedding", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(
        "text", DataType.VARCHAR, max_length=65535,
        enable_analyzer=True, analyzer_params={"type": "chinese"},
        enable_match=True,
    )
    schema.add_field("filename", DataType.VARCHAR, max_length=255)
    schema.add_field("file_type", DataType.VARCHAR, max_length=50)
    schema.add_field("file_path", DataType.VARCHAR, max_length=1024)
    schema.add_field("page_number", DataType.INT64)
    schema.add_field("chunk_idx", DataType.INT64)
    schema.add_field("chunk_id", DataType.VARCHAR, max_length=512)
    schema.add_field("parent_chunk_id", DataType.VARCHAR, max_length=512)
    schema.add_field("root_chunk_id", DataType.VARCHAR, max_length=512)
    schema.add_field("chunk_level", DataType.INT64)

    bm25_function = Function(
        name="text_bm25_emb", function_type=FunctionType.BM25,
        input_field_names=["text"], output_field_names=["sparse_embedding"],
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense_embedding", index_type="HNSW",
        metric_type="IP", params={"M": 16, "efConstruction": 256},
    )
    index_params.add_index(
        field_name="sparse_embedding", index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25", params={"drop_ratio_build": 0.2},
    )

    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    print("✅ 集合创建成功！")

print("所有集合:", client.list_collections())
client.close()