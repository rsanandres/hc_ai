ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
    vector_store = await PGVectorStore.create(
        engine=engine,
        table_name="hc_ai_table",
        schema_name="hc_ai_schema",
        embedding_service=embedding,
    )

if __name__ == "__main__":
    asyncio.run(main())
    await vector_store.close()