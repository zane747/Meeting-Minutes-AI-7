"""臨時 DB 檢查腳本，用完可刪。"""
import sqlite3

c = sqlite3.connect("meeting_minutes.db")
tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)
print("has topics:", "topics" in tables)

if "topics" in tables:
    print("topics count:", c.execute("SELECT count(*) FROM topics").fetchone()[0])
    for row in c.execute("SELECT id, title FROM topics LIMIT 5").fetchall():
        print(" ", row)
else:
    print("topics table NOT FOUND - need to delete DB and restart uvicorn")

if "meetings" in tables:
    for row in c.execute("SELECT id, status, title FROM meetings").fetchall():
        print("meeting:", row)
