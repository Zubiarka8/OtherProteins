"""Quick script to verify database structure."""

import sqlite3
from database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=== Datu-basearen taulak ===")
for table in tables:
    print(f"\n{table[0]}:")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

# Show sample data counts
print("\n=== Datuak ===")
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cursor.fetchone()[0]
    print(f"{table[0]}: {count} erregistro")

conn.close()



