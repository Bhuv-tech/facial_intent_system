import sqlite3
import os

db_path = r'c:\Users\bhuva\OneDrive\Desktop\Facial_Intent_System\data\assistive_system.db'

if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Find the canonical ID for bhuvanam66s@gmail.com
# We'll pick 91 as the professional ID since the user is trying to host
canonical_id = 91
old_id = 88

print(f"Consolidating sessions from {old_id} to {canonical_id}...")

# Update sessions
cursor.execute("UPDATE sessions SET professional_id = ? WHERE professional_id = ?", (canonical_id, old_id))
rows_updated = cursor.rowcount
print(f"Updated {rows_updated} sessions.")

# Update session participants just in case
cursor.execute("UPDATE session_participants SET participant_id = ? WHERE participant_id = ?", (canonical_id, old_id))
print(f"Updated {cursor.rowcount} participant records.")

# Clean up duplicate user if they have the same email and we want one account
# cursor.execute("DELETE FROM users WHERE id = ?", (old_id,)) 
# Actually, let's keep them but ensure they don't block each other.

conn.commit()
conn.close()
print("Fix applied.")
