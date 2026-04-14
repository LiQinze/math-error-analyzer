"""
SQLite 存储层：保存错题记录
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.expanduser("~/math-error-analyzer/error_records.db")


def init_db():
    """建表"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            create table if not exists error_records (
                id INTEGER primary key autoincrement,
                created_at TEXT default (datetime('now', '+8 hours')),
                subject TEXT,
                grade TEXT,
                error_type TEXT,
                knowledge_point TEXT,
                root_cause TEXT,
                correct_solution TEXT,
                similar_problems TEXT,
                memory_tip TEXT,
                confidence REAL,
                raw_result TEXT,
                image_b64 TEXT
            )
        """)
        conn.execute("""
            create table if not exists stats_summary (
                id INTEGER primary key autoincrement,
                date TEXT default (date('now', '+8 hours')),
                error_type TEXT,
                count INTEGER default 1
            )
        """)


def save_record(result_json: str, image_b64: str = None) -> int:
    """解析 JSON 并存入数据库，返回记录 ID"""
    import api_client

    # 提取 JSON（可能包含多余文字）
    import re
    match = re.search(r'\{.*\}', result_json, re.DOTALL)
    if not match:
        raise ValueError(f"无法解析 AI 返回内容: {result_json[:100]}")

    data = json.loads(match.group())

    # 写入主表
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            insert into error_records (
                subject, grade, error_type, knowledge_point,
                root_cause, correct_solution, similar_problems,
                memory_tip, confidence, raw_result, image_b64
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("subject"),
            data.get("grade"),
            data.get("error_type"),
            data.get("knowledge_point"),
            data.get("root_cause"),
            data.get("correct_solution"),
            json.dumps(data.get("similar_problems", []), ensure_ascii=False),
            data.get("memory_tip"),
            data.get("confidence"),
            result_json,
            image_b64,
        ))
        record_id = cur.lastrowid

        # 统计表
        error_type = data.get("error_type", "未知")
        today = datetime.now().strftime("%Y-%m-%d")
        existing = conn.execute(
            "select id, count from stats_summary where date=? and error_type=?",
            (today, error_type)
        ).fetchone()
        if existing:
            conn.execute(
                "update stats_summary set count=? where id=?",
                (existing[1] + 1, existing[0])
            )
        else:
            conn.execute(
                "insert into stats_summary (date, error_type, count) values (?, ?, 1)",
                (today, error_type)
            )

    return record_id


def get_records(limit: int = 50) -> list:
    """获取最近 N 条记录"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "select * from error_records order by created_at desc limit ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> list:
    """获取今日统计"""
    today = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(r) for r in conn.execute(
                "select error_type, count from stats_summary where date=? order by count desc",
                (today,)
            ).fetchall()
        ]


# 启动时自动建表
init_db()
