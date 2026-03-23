import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

dsn = os.getenv("DATABASE_URL")
sslmode = os.getenv("PGSSLMODE", "require")

migrations_dir = Path(__file__).parent / "db" / "migrations"

with psycopg.connect(dsn, sslmode=sslmode) as conn:
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        print(f"Running {sql_file.name}...")
        conn.execute(sql_file.read_text())
    conn.commit()
    print("All migrations applied successfully.")
