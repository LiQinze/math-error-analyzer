"""
SQLite 存储层：保存错题记录
"""

import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.environ.get("DATABASE_PATH") or os.path.expanduser("~/math-error-analyzer/error_records.db")
BEIJING_TZ = timezone(timedelta(hours=8))


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            create table if not exists error_records (
                id INTEGER primary key autoincrement,
                created_at TEXT default (datetime('now', '+8 hours')),
                subject TEXT, grade TEXT, error_type TEXT, knowledge_point TEXT,
                root_cause TEXT, correct_solution TEXT, similar_problems TEXT,
                memory_tip TEXT, confidence REAL, raw_result TEXT, image_b64 TEXT
            )
        """)
        conn.execute("""
            create table if not exists stats_summary (
                id INTEGER primary key autoincrement,
                date TEXT default (date('now', '+8 hours')),
                error_type TEXT, count INTEGER default 1
            )
        """)


def save_record(result_json: str, image_b64: str = None) -> int:
    import re
    match = re.search(r'\{.*\}', result_json, re.DOTALL)
    if not match:
        raise ValueError(f"无法解析 AI 返回内容: {result_json[:100]}")
    data = json.loads(match.group())
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            insert into error_records (
                subject, grade, error_type, knowledge_point,
                root_cause, correct_solution, similar_problems,
                memory_tip, confidence, raw_result, image_b64
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("subject"), data.get("grade"), data.get("error_type"),
            data.get("knowledge_point"), data.get("root_cause"),
            data.get("correct_solution"),
            json.dumps(data.get("similar_problems", []), ensure_ascii=False),
            data.get("memory_tip"), data.get("confidence"),
            result_json, image_b64,
        ))
        record_id = cur.lastrowid
        error_type = data.get("error_type", "未知")
        today = datetime.now(tz=BEIJING_TZ).strftime("%Y-%m-%d")
        existing = conn.execute(
            "select id, count from stats_summary where date=? and error_type=?",
            (today, error_type)
        ).fetchone()
        if existing:
            conn.execute("update stats_summary set count=? where id=?",
                         (existing[1] + 1, existing[0]))
        else:
            conn.execute("insert into stats_summary (date, error_type, count) values (?, ?, 1)",
                         (today, error_type))
    return record_id


def get_records(limit: int = 50) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "select * from error_records order by created_at desc limit ?",
            (limit,)
        ).fetchall()]


def get_stats() -> list:
    today = datetime.now(tz=BEIJING_TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "select error_type, count from stats_summary where date=? order by count desc",
            (today,)
        ).fetchall()]


init_db()
