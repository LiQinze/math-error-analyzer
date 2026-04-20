"""SQLite/PostgreSQL 存储层，通过 DATABASE_URL 环境变量自动选择。
main.py 调用接口: save_record(ai_raw_text, image_b64)
"""

import json, os, re, sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

BEIJING_TZ = timezone(timedelta(hours=8))
_use_pg = bool(os.environ.get("DATABASE_URL"))

# ── PostgreSQL ──────────────────────────────────────────────
if _use_pg:
    import psycopg
    DB_URL = os.environ["DATABASE_URL"]
    def _pg():
        return psycopg.connect(DB_URL)

    def init_db() -> None:
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS error_records (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT (now() AT TIME ZONE 'Asia/Shanghai'),
                    subject TEXT, grade TEXT, problem_text TEXT,
                    error_type TEXT, knowledge_point TEXT, root_cause TEXT,
                    error_reason TEXT, error_behavior TEXT, step_stage TEXT,
                    correct_solution TEXT, similar_problems TEXT,
                    memory_tip TEXT, confidence REAL,
                    raw_result TEXT, analysis_json TEXT, image_b64 TEXT)""")
                cur.execute("""CREATE TABLE IF NOT EXISTS stats_summary (
                    id SERIAL PRIMARY KEY,
                    date DATE DEFAULT (current_date AT TIME ZONE 'Asia/Shanghai'),
                    error_type TEXT, count INTEGER DEFAULT 1)""")
            conn.commit()

    def health_snapshot() -> dict[str, Any]:
        try:
            with _pg() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM error_records")
                    count = cur.fetchone()[0]
            return {"db_path": "PostgreSQL", "db_exists": True,
                    "db_writable": True, "db_size_bytes": 0,
                    "record_count": int(count), "last_write": {"ok": True}}
        except Exception as e:
            return {"db_writable": False, "error": str(e)}

    def save_record(ai_raw_text: str, img_b64: str | None = None) -> int:
        """解析 ai_raw_text (JSON 字符串) 并存入 PostgreSQL"""
        match = re.search(r'\{.*\}', ai_raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"无法解析 AI 返回内容: {ai_raw_text[:100]}")
        data = json.loads(match.group())
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO error_records
                    (subject, grade, problem_text, error_type, knowledge_point, root_cause,
                     error_reason, error_behavior, step_stage, correct_solution,
                     similar_problems, memory_tip, confidence, raw_result, analysis_json, image_b64)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id""", (
                    data.get("subject"), data.get("grade"), data.get("problem_text"),
                    data.get("error_type"), data.get("knowledge_point"), data.get("root_cause"),
                    data.get("error_reason"), data.get("error_behavior"), data.get("step_stage"),
                    data.get("correct_solution"),
                    json.dumps(data.get("similar_problems", []), ensure_ascii=False),
                    data.get("memory_tip"), data.get("confidence"),
                    ai_raw_text, json.dumps(data, ensure_ascii=False), img_b64))
                record_id = cur.fetchone()[0]
                today = datetime.now(tz=BEIJING_TZ).strftime("%Y-%m-%d")
                et = data.get("error_type", "未知")
                cur.execute("SELECT id,count FROM stats_summary WHERE date=%s AND error_type=%s", (today, et))
                r = cur.fetchone()
                if r: cur.execute("UPDATE stats_summary SET count=%s WHERE id=%s", (r[1]+1, r[0]))
                else: cur.execute("INSERT INTO stats_summary (date,error_type,count) VALUES (%s,%s,1)", (today, et))
            conn.commit()
        return record_id

    def get_records(limit: int = 50) -> list[dict[str, Any]]:
        with _pg() as conn:
            with conn.cursor(name="c") as cur:
                cur.execute("SELECT * FROM error_records ORDER BY created_at DESC LIMIT %s", (limit,))
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _dates(days: int) -> list[str]:
        d = datetime.now(tz=BEIJING_TZ).date()
        return [(d - timedelta(days=i)).isoformat() for i in range(days-1, -1, -1)]

    def get_stats(days: int = 7) -> dict[str, Any]:
        days = max(1, min(days, 60))
        dates = _dates(days); s = dates[0]
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(error_type,''), COUNT(*) FROM error_records WHERE DATE(created_at) >= %s GROUP BY 1 ORDER BY 2 DESC", (s,))
                ets = [{"error_type": r[0], "count": r[1]} for r in cur.fetchall()]
                cur.execute("SELECT COALESCE(error_reason,''), COUNT(*) FROM error_records WHERE DATE(created_at) >= %s AND error_reason IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 8", (s,))
                ers = [{"error_reason": r[0], "count": r[1]} for r in cur.fetchall()]
                cur.execute("SELECT COALESCE(error_behavior,''), COUNT(*) FROM error_records WHERE DATE(created_at) >= %s AND error_behavior IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 8", (s,))
                ebs = [{"error_behavior": r[0], "count": r[1]} for r in cur.fetchall()]
                cur.execute("SELECT COALESCE(knowledge_point,''), COUNT(*) FROM error_records WHERE DATE(created_at) >= %s AND knowledge_point IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10", (s,))
                kps = [{"knowledge_point": r[0], "count": r[1]} for r in cur.fetchall()]
                cur.execute("SELECT DATE(created_at), COUNT(*), AVG(COALESCE(confidence,0)) FROM error_records WHERE DATE(created_at) >= %s GROUP BY 1 ORDER BY 1 ASC", (s,))
                rows = cur.fetchall()
        dm = {str(r[0]): {"day": str(r[0]), "total": r[1], "avg_confidence": round(float(r[2]), 3)} for r in rows}
        trend = [{"day": d, "total": dm.get(d, {}).get("total", 0), "avg_confidence": dm.get(d, {}).get("avg_confidence", 0.0)} for d in dates]
        return {"days": days, "error_types": ets, "error_reasons": ers, "error_behaviors": ebs, "knowledge_points": kps, "trend": trend}

    def get_summary_dataset(days: int = 7, limit: int = 12) -> dict[str, Any]:
        stats = get_stats(days); s = _dates(days)[0]
        with _pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT created_at::text, error_type, knowledge_point, root_cause, correct_solution FROM error_records WHERE DATE(created_at) >= %s ORDER BY created_at DESC LIMIT %s", (s, limit))
                rows = cur.fetchall()
        samples = [{"created_at": str(r[0]), "error_type": r[1], "knowledge_point": r[2], "root_cause": r[3], "correct_solution": r[4]} for r in rows]
        return {"stats": stats, "samples": samples}

# ── SQLite fallback ──────────────────────────────────────────
else:
    def _resolve() -> str:
        for k in ("DB_FILE", "RENDER_DISK_PATH", "DB_DIR"):
            v = os.environ.get(k, "").strip()
            if not v: continue
            return v if k == "DB_FILE" else (os.path.join(v, "error_records.db") if not v.endswith(".db") else v)
        return os.path.join(os.environ.get("HOME") or os.path.expanduser("~"), "math-error-analyzer", "error_records.db")

    DB_PATH = _resolve()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    LAST_WRITE: dict[str, Any] = {"ok": False, "record_id": None, "error": "", "ts": ""}

    def _conn() -> sqlite3.Connection:
        c = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL"); c.row_factory = sqlite3.Row
        return c

    def _col(conn: sqlite3.Connection, t: str, c: str, ddl: str) -> None:
        cs = {r["name"] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()}
        if c not in cs: conn.execute(f"ALTER TABLE {t} ADD COLUMN {c} {ddl}")

    def init_db() -> None:
        with _conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS error_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now', '+8 hours')),
                subject TEXT, grade TEXT, problem_text TEXT,
                error_type TEXT, knowledge_point TEXT, root_cause TEXT,
                error_reason TEXT, error_behavior TEXT, step_stage TEXT,
                correct_solution TEXT, similar_problems TEXT,
                memory_tip TEXT, confidence REAL,
                raw_result TEXT, analysis_json TEXT, image_b64 TEXT)""")
            for c, d in [("problem_text","TEXT"),("error_reason","TEXT"),("error_behavior","TEXT"),("step_stage","TEXT"),("analysis_json","TEXT")]:
                _col(conn, "error_records", c, d)

    def health_snapshot() -> dict[str, Any]:
        e = os.path.exists(DB_PATH); w = os.access(os.path.dirname(DB_PATH), os.W_OK)
        return {"db_path": DB_PATH, "db_exists": e, "db_writable": w,
                "db_size_bytes": os.path.getsize(DB_PATH) if e else 0,
                "last_write": LAST_WRITE, "model": {"configured": True}}

    def save_record(ai_raw_text: str, img_b64: str | None = None) -> int:
        match = re.search(r'\{.*\}', ai_raw_text, re.DOTALL)
        if not match: raise ValueError(f"无法解析 AI 返回内容: {ai_raw_text[:100]}")
        data = json.loads(match.group())
        with _conn() as conn:
            cur = conn.execute("""INSERT INTO error_records
                (subject, grade, problem_text, error_type, knowledge_point, root_cause,
                 error_reason, error_behavior, step_stage, correct_solution,
                 similar_problems, memory_tip, confidence, raw_result, analysis_json, image_b64)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get("subject"), data.get("grade"), data.get("problem_text"),
                 data.get("error_type"), data.get("knowledge_point"), data.get("root_cause"),
                 data.get("error_reason"), data.get("error_behavior"), data.get("step_stage"),
                 data.get("correct_solution"),
                 json.dumps(data.get("similar_problems", []), ensure_ascii=False),
                 data.get("memory_tip"), data.get("confidence"),
                 ai_raw_text, json.dumps(data, ensure_ascii=False), img_b64))
            record_id = int(cur.lastrowid)
        LAST_WRITE.update({"ok": True, "record_id": record_id, "error": "", "ts": datetime.now(BEIJING_TZ).isoformat()})
        return record_id

    def get_records(limit: int = 50) -> list[dict[str, Any]]:
        with _conn() as conn:
            rows = conn.execute("SELECT * FROM error_records ORDER BY datetime(created_at) DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for f in ("similar_problems", "analysis_json"):
                try: d[f] = json.loads(d.get(f) or "{}")
                except json.JSONDecodeError: d[f] = {} if f == "analysis_json" else []
            result.append(d)
        return result

    def _dates(days: int) -> list[str]:
        d = datetime.now(BEIJING_TZ).date()
        return [(d - timedelta(days=i)).isoformat() for i in range(days-1, -1, -1)]

    def get_stats(days: int = 7) -> dict[str, Any]:
        days = max(1, min(days, 60)); dates = _dates(days); s = dates[0]
        with _conn() as conn:
            ets = [dict(r) for r in conn.execute("SELECT COALESCE(error_type,''), COUNT(*) FROM error_records WHERE date(created_at) >= ? GROUP BY 1 ORDER BY 2 DESC", (s,)).fetchall()]
            ers = [dict(r) for r in conn.execute("SELECT COALESCE(error_reason,''), COUNT(*) FROM error_records WHERE date(created_at) >= ? AND IFNULL(error_reason,'') <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 8", (s,)).fetchall()]
            ebs = [dict(r) for r in conn.execute("SELECT COALESCE(error_behavior,''), COUNT(*) FROM error_records WHERE date(created_at) >= ? AND IFNULL(error_behavior,'') <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 8", (s,)).fetchall()]
            kps = [dict(r) for r in conn.execute("SELECT COALESCE(knowledge_point,''), COUNT(*) FROM error_records WHERE date(created_at) >= ? AND IFNULL(knowledge_point,'') <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 10", (s,)).fetchall()]
            rows = conn.execute("SELECT date(created_at), COUNT(*), AVG(COALESCE(confidence,0)) FROM error_records WHERE date(created_at) >= ? GROUP BY 1 ORDER BY 1 ASC", (s,)).fetchall()
        dm = {r[0]: {"day": r[0], "total": r[1], "avg_confidence": round(float(r[2]), 3)} for r in rows}
        trend = [{"day": d, "total": dm.get(d, {}).get("total", 0), "avg_confidence": dm.get(d, {}).get("avg_confidence", 0.0)} for d in dates]
        return {"days": days, "error_types": ets, "error_reasons": ers, "error_behaviors": ebs, "knowledge_points": kps, "trend": trend}

    def get_summary_dataset(days: int = 7, limit: int = 12) -> dict[str, Any]:
        stats = get_stats(days); s = _dates(days)[0]
        with _conn() as conn:
            rows = conn.execute("SELECT created_at, COALESCE(error_type,''), COALESCE(knowledge_point,''), COALESCE(root_cause,''), COALESCE(correct_solution,'') FROM error_records WHERE date(created_at) >= ? ORDER BY datetime(created_at) DESC LIMIT ?", (s, limit)).fetchall()
        samples = [{"created_at": str(r[0]), "error_type": r[1], "knowledge_point": r[2], "root_cause": r[3], "correct_solution": r[4]} for r in rows]
        return {"stats": stats, "samples": samples}

init_db()
