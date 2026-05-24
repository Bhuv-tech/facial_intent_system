import sqlite3
import os

db_path = r'c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\data\assistive_system.db'

if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- USERS ---")
cursor.execute("SELECT id, name, email, role, user_type FROM users")
for row in cursor.fetchall():
    print(dict(row))

print("\n--- SESSIONS ---")
cursor.execute("SELECT session_id, professional_id, status FROM sessions")
for row in cursor.fetchall():
    print(dict(row))

conn.close()
