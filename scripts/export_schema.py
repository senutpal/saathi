import sqlite3
import os

def export_schema():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, "instance", "saathi.db")
    sql_path = os.path.join(base_dir, "schema.sql")
    dbml_path = os.path.join(base_dir, "schema.dbml")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Export standard SQL
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%';")
    tables_sql = [row[0] for row in cur.fetchall()]

    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("-- Saathi SQLite Database Schema\n\n")
        for table_sql in tables_sql:
            f.write(table_sql.strip() + ";\n\n")

    # 2. Export DBML (native syntax for dbdiagram.io)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    table_names = [row[0] for row in cur.fetchall()]

    dbml_lines = ["// Saathi Database Diagram (DBML)", "// Paste this directly into https://dbdiagram.io\n"]
    relationships = []

    for tname in table_names:
        cur.execute(f"PRAGMA table_info('{tname}');")
        cols = cur.fetchall() # cid, name, type, notnull, dflt_value, pk

        cur.execute(f"PRAGMA foreign_key_list('{tname}');")
        fks = cur.fetchall() # id, seq, table, from, to, on_update, on_delete, match

        for fk in fks:
            target_table = fk[2]
            from_col = fk[3]
            to_col = fk[4]
            relationships.append(f"Ref: {tname}.{from_col} > {target_table}.{to_col}")

        dbml_lines.append(f"Table {tname} {{")
        for col in cols:
            c_name = col[1]
            c_type = col[2] if col[2] else "varchar"
            is_pk = bool(col[5])
            is_notnull = bool(col[3])

            props = []
            if is_pk:
                props.append("pk")
            if is_notnull and not is_pk:
                props.append("not null")

            prop_str = f" [{', '.join(props)}]" if props else ""
            dbml_lines.append(f"  {c_name} {c_type}{prop_str}")
        dbml_lines.append("}\n")

    if relationships:
        dbml_lines.append("// Relationships")
        for rel in set(relationships):
            dbml_lines.append(rel)

    with open(dbml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(dbml_lines) + "\n")

    print(f"Exported {len(tables_sql)} tables:")
    print(f"  1. SQL Schema: {sql_path}")
    print(f"  2. DBML File:   {dbml_path}")

if __name__ == "__main__":
    export_schema()
