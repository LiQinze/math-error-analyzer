"""
SQLite 存储层 — 支持 Render 持久化磁盘
"""

import sqlite3, json, os
from datetime import datetime, timezone, timedelta

# Render 免费版：/tmp 会丢失，改为使用持久化路径
DB_PATH = os.environ.get("RENDER_DISK_PATH") or os.path.join(os.environ.get("HOME", "/root"), "math-error-analyzer", "error_records.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
BEIJING_TZ = timezone(timedelta(hours=8))


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS error_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now', '+8 hours')),
            subject TEXT, grade TEXT, error_type TEXT, knowledge_point TEXT,
            root_cause TEXT, correct_solution TEXT, similar_problems TEXT,
            memory_tip TEXT, confidence REAL, raw_result TEXT, image_b64 TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS stats_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT (date('now', '+8 hours')),
            error_type TEXT, count INTEGER DEFAULT 1
        )""")


def save_record(result_json: str, image_b64: str = None) -> int:
    import re
    match = re.search(r'\{.*\}', result_json, re.DOTALL)
    if not match:
        raise ValueError(f"无法解析 AI 返回内容: {result_json[:100]}")
    data = json.loads(match.group())
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""INSERT INTO error_records
            (subject, grade, error_type, knowledge_point, root_cause,
             correct_solution, similar_problems, memory_tip, confidence, raw_result, image_b64)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.get("subject"), data.get("grade"), data.get("error_type"),
             data.get("knowledge_point"), data.get("root_cause"),
             data.get("correct_solution"),
             json.dumps(data.get("similar_problems", []), ensure_ascii=False),
             data.get("memory_tip"), data.get("confidence"),
             result_json, image_b64))
        record_id = cur.lastrowid
        today = datetime.now(tz=BEIJING_TZ).strftime("%Y-%m-%d")
        et = data.get("error_type", "未知")
        ex = conn.execute("SELECT id,count FROM stats_summary WHERE date=? AND error_type=?", (today, et)).fetchone()
        if ex:
            conn.execute("UPDATE stats_summary SET count=? WHERE id=?", (ex[1] + 1, ex[0]))
        else:
            conn.execute("INSERT INTO stats_summary (date,error_type,count) VALUES (?,?,1)", (today, et))
    return record_id


def get_records(limit: int = 50) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT * FROM error_records ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_stats() -> list:
    today = datetime.now(tz=BEIJING_TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT error_type,count FROM stats_summary WHERE date=? ORDER BY count DESC", (today,)
        ).fetchall()]


init_db()
