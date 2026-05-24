import sqlite3
import os

dbs = [
    r'c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\backend\database\assistive_system.db',
    r'c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\data\assistive_system.db'
]

def check_rakshan():
    print("Listing databases and searching for 'Rakshan'...")
    for db in dbs:
        if not os.path.exists(db):
            print(f"[-] {db} (Does not exist)")
            continue
        
        print(f"[+] Found: {db}")
        try:
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE name LIKE ?", ("%rakshan%",))
            rows = cursor.fetchall()
            if rows:
                print(f"    - FOUND RAKSHAN in this database:")
                for row in rows:
                    print(f"      ID: {row['id']}, Name: {row['name']}, Email: {row['email']}, Type: {row['user_type']}")
            else:
                print(f"    - Rakshan NOT found here.")
            conn.close()
        except Exception as e:
            print(f"    - Error reading database: {e}")

if __name__ == "__main__":
    check_rakshan()
