from app.database.connection import PROJECT_ROOT, get_connection

SCHEMA_PATH = PROJECT_ROOT / "app" / "database" / "db.sql"

def create_tables(connection):
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.execute(schema_sql)

def main():
    with get_connection() as connection:
        create_tables(connection)
    print("Database initialized")


if __name__ == "__main__":
    main()
