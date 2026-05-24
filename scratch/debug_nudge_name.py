import sqlite3
import os

db_path = r'c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\data\assistive_system.db'

def inspect():
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("--- Searching for ID 87 or 'rakshan' ---")
    cursor.execute("SELECT * FROM users WHERE id = 87 OR name LIKE ?", ("%rakshan%",))
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))

    if not rows:
        print("No matching users found.")
        print("\n--- Recent Students ---")
        cursor.execute("SELECT id, name, user_type FROM users WHERE user_type = 'student' ORDER BY id DESC LIMIT 5")
        for row in cursor.fetchall():
            print(dict(row))

    conn.close()

if __name__ == "__main__":
    inspect()
