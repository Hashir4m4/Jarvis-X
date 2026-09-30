import sqlite3
import logging
import os
import datetime

logger = logging.getLogger(__name__)

class SQLiteManager:
    def __init__(self, config: dict):
        self.db_path = config.get("sqlite_db_path", "memory/database_storage/jarvis.sqlite")
        
        # Ensure directory exists
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)
        
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        try:
            cursor = self.conn.cursor()
            
            # User profile table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME
                )
            ''')
            
            # Projects memory table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    path TEXT,
                    description TEXT,
                    last_accessed DATETIME
                )
            ''')
            
            self.conn.commit()
            logger.info("SQLite tables created/verified.")
        except Exception as e:
            logger.error(f"Failed to create SQLite tables: {e}")

    def add_message(self, session_id: str, role: str, content: str) -> int:
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, timestamp)
            )
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error adding message to SQLite: {e}")
            return -1

    def get_recent_messages(self, session_id: str, limit: int = 20) -> list:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            # Reverse to maintain chronological order
            return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
        except Exception as e:
            logger.error(f"Error fetching messages from SQLite: {e}")
            return []

    def set_user_pref(self, key: str, value: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)",
                (key, value)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error setting user preference: {e}")

    def get_user_pref(self, key: str) -> str:
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
        except Exception as e:
            logger.error(f"Error getting user preference: {e}")
            return None

    def close(self):
        self.conn.close()
