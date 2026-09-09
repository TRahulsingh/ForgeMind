import sqlite3
import json
from pathlib import Path
from datetime import datetime
from backend.core.config import settings

DB_PATH = Path(settings.database_path)

def get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode for concurrent 15-task benchmark
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except:
        pass
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_request TEXT,
            status TEXT,
            state_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT PRIMARY KEY,
            data TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_task(task_id: str, user_request: str, status: str, state: dict):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT INTO tasks (id, user_request, status, state_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET status=?, state_json=?, updated_at=?
    """, (task_id, user_request, status, json.dumps(state), now, now, status, json.dumps(state), now))
    conn.commit()
    conn.close()

def get_task(task_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def list_tasks(limit=20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

init_db()
