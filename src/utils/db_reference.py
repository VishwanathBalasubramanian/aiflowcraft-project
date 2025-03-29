def get_db_reference_data(config: dict) -> str:
    import sqlite3

    db_type = config.get("db_type")
    db_path = config.get("db_path")
    print("🔎 DB Type:", db_type)
    print("📁 DB Path:", db_path)

    if db_type != "sqlite" or not db_path:
        return ""

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("📊 Tables found:", tables)

        if not tables:
            return ""

        # Pick the first table
        table_name = tables[0][0]
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]

        result = "\n".join([str(dict(zip(col_names, row))) for row in rows])
        conn.close()
        return result

    except Exception as e:
        print("❌ DB ERROR:", e)
        return ""
