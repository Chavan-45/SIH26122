import sqlite3

conn = sqlite3.connect('sih26122.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print("EXISTING TABLES IN sih26122.db:")
for t in tables:
    print(f" - {t}")
    cursor.execute(f"PRAGMA table_info('{t}')")
    cols = [f"{c[1]} ({c[2]})" for c in cursor.fetchall()]
    print(f"   Columns: {', '.join(cols)}")

conn.close()
