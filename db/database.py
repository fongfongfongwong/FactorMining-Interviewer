"""Database layer — PostgreSQL (production) with SQLite fallback (local dev).

Set DATABASE_URL env var for PostgreSQL, otherwise falls back to SQLite.
"""

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

# ── Connection setup ──

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

if USE_PG:
    import psycopg2
    import psycopg2.extras
    from psycopg2.pool import ThreadedConnectionPool

    # Fix Supabase/Railway URL scheme
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    _pool = None

    def _get_pool():
        global _pool
        if _pool is None:
            _pool = ThreadedConnectionPool(1, 10, DATABASE_URL)
        return _pool
else:
    import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "interviewer.db")


def _ensure_db_dir():
    if not USE_PG:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


class _DictRow(dict):
    """Make dict act like sqlite3.Row for compatibility."""
    pass


@contextmanager
def get_connection():
    """Get a database connection (PostgreSQL or SQLite)."""
    if USE_PG:
        pool = _get_pool()
        conn = pool.getconn()
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)
    else:
        _ensure_db_dir()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _execute(conn, sql, params=None):
    """Execute SQL with PostgreSQL/SQLite compatibility."""
    if USE_PG:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()

    if params:
        if USE_PG:
            # Convert ? placeholders to %s for PostgreSQL
            sql = sql.replace("?", "%s")
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    return cur


def _fetchall(cur):
    rows = cur.fetchall()
    if USE_PG:
        return [dict(r) for r in rows]
    return [dict(r) for r in rows]


def _fetchone(cur):
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def _lastrowid(conn, cur):
    if USE_PG:
        return cur.fetchone()["id"]
    return cur.lastrowid


# ── Schema init ──

def init_db():
    """Create all tables."""
    with get_connection() as conn:
        if USE_PG:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'operator')),
                    display_name TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS invite_links (
                    id SERIAL PRIMARY KEY,
                    token TEXT UNIQUE NOT NULL,
                    candidate_name TEXT,
                    candidate_email TEXT,
                    track TEXT,
                    expires_at TIMESTAMPTZ,
                    used_at TIMESTAMPTZ,
                    created_by INTEGER REFERENCES users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS candidates (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    resume_filename TEXT,
                    resume_text TEXT,
                    parsed_data TEXT,
                    scores TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS exam_sessions (
                    id SERIAL PRIMARY KEY,
                    candidate_id INTEGER REFERENCES candidates(id),
                    track TEXT NOT NULL,
                    status TEXT DEFAULT 'not_started',
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ,
                    time_limit_minutes INTEGER DEFAULT 120,
                    total_score REAL,
                    max_score REAL,
                    score_breakdown TEXT,
                    current_question_index INTEGER DEFAULT 0,
                    answers_json TEXT DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS answers (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES exam_sessions(id),
                    question_id TEXT NOT NULL,
                    response TEXT,
                    is_correct INTEGER,
                    score REAL,
                    max_score REAL,
                    grading_notes TEXT,
                    flagged_for_review INTEGER DEFAULT 0,
                    answered_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS question_stats (
                    question_id TEXT PRIMARY KEY,
                    times_shown INTEGER DEFAULT 0,
                    times_correct INTEGER DEFAULT 0,
                    avg_score REAL DEFAULT 0,
                    avg_time_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id TEXT,
                    details TEXT,
                    ip_address TEXT
                );
            """)
            conn.commit()
        else:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'operator')),
                    display_name TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    is_active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS invite_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    candidate_name TEXT,
                    candidate_email TEXT,
                    track TEXT,
                    expires_at TEXT,
                    used_at TEXT,
                    created_by INTEGER REFERENCES users(id),
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    resume_filename TEXT,
                    resume_text TEXT,
                    parsed_data TEXT,
                    scores TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS exam_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER,
                    track TEXT NOT NULL,
                    status TEXT DEFAULT 'not_started',
                    started_at TEXT,
                    finished_at TEXT,
                    time_limit_minutes INTEGER DEFAULT 120,
                    total_score REAL,
                    max_score REAL,
                    score_breakdown TEXT,
                    current_question_index INTEGER DEFAULT 0,
                    answers_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
                );

                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    question_id TEXT NOT NULL,
                    response TEXT,
                    is_correct INTEGER,
                    score REAL,
                    max_score REAL,
                    grading_notes TEXT,
                    flagged_for_review INTEGER DEFAULT 0,
                    answered_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (session_id) REFERENCES exam_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS question_stats (
                    question_id TEXT PRIMARY KEY,
                    times_shown INTEGER DEFAULT 0,
                    times_correct INTEGER DEFAULT 0,
                    avg_score REAL DEFAULT 0,
                    avg_time_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id TEXT,
                    details TEXT,
                    ip_address TEXT
                );
            """)


# ── User CRUD ──

def create_user(username, password_hash, role, display_name=""):
    with get_connection() as conn:
        cur = _execute(conn,
            "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)" + (" RETURNING id" if USE_PG else ""),
            (username, password_hash, role, display_name))
        return _lastrowid(conn, cur)


def get_user_by_username(username):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM users WHERE username = ? AND is_active = ?", (username, True if USE_PG else 1))
        return _fetchone(cur)


def get_all_users():
    with get_connection() as conn:
        cur = _execute(conn, "SELECT id, username, role, display_name, created_at, is_active FROM users ORDER BY created_at DESC")
        return _fetchall(cur)


def deactivate_user(user_id):
    with get_connection() as conn:
        _execute(conn, "UPDATE users SET is_active = ? WHERE id = ?", (False if USE_PG else 0, user_id))


# ── Invite Links ──

def _generate_short_code():
    """Generate a unique 4-digit invite code."""
    import random
    for _ in range(100):
        code = str(random.randint(1000, 9999))
        existing = get_invite_link(code)
        if not existing:
            return code
    # Fallback to 6 digits if all 4-digit codes exhausted
    return str(random.randint(100000, 999999))


def create_invite_link(candidate_name="", candidate_email="", track=None, created_by=None, expires_hours=72):
    token = _generate_short_code()
    expires_at = (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat()
    with get_connection() as conn:
        cur = _execute(conn,
            "INSERT INTO invite_links (token, candidate_name, candidate_email, track, expires_at, created_by) VALUES (?, ?, ?, ?, ?, ?)" + (" RETURNING id" if USE_PG else ""),
            (token, candidate_name, candidate_email, track, expires_at, created_by))
        return token


def get_invite_link(token):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM invite_links WHERE token = ?", (token,))
        return _fetchone(cur)


def mark_invite_used(token):
    with get_connection() as conn:
        now = datetime.utcnow().isoformat()
        _execute(conn, "UPDATE invite_links SET used_at = ? WHERE token = ?", (now, token))


def get_all_invite_links():
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM invite_links ORDER BY created_at DESC")
        return _fetchall(cur)


# ── Candidate CRUD ──

def insert_candidate_manual(name, school="", track=""):
    parsed_data = {"name": name, "education": [{"school": school}] if school else [], "skills": [], "experience": [], "competitions": [], "publications": [], "summary": "手动录入 — {}".format(track)}
    with get_connection() as conn:
        cur = _execute(conn,
            "INSERT INTO candidates (name, email, phone, resume_filename, resume_text, parsed_data, scores) VALUES (?, ?, ?, ?, ?, ?, ?)" + (" RETURNING id" if USE_PG else ""),
            (name, "", "", "", "", json.dumps(parsed_data, ensure_ascii=False), "{}"))
        return _lastrowid(conn, cur)


def insert_candidate(name, email, phone, resume_filename, resume_text, parsed_data, scores):
    with get_connection() as conn:
        cur = _execute(conn,
            "INSERT INTO candidates (name, email, phone, resume_filename, resume_text, parsed_data, scores) VALUES (?, ?, ?, ?, ?, ?, ?)" + (" RETURNING id" if USE_PG else ""),
            (name, email, phone, resume_filename, resume_text,
             json.dumps(parsed_data, ensure_ascii=False),
             json.dumps(scores, ensure_ascii=False)))
        return _lastrowid(conn, cur)


def get_all_candidates():
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM candidates ORDER BY created_at DESC")
        return _fetchall(cur)


def get_candidate(candidate_id):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM candidates WHERE id = ?", (candidate_id,))
        return _fetchone(cur)


def delete_candidate(candidate_id):
    with get_connection() as conn:
        _execute(conn, "DELETE FROM answers WHERE session_id IN (SELECT id FROM exam_sessions WHERE candidate_id = ?)", (candidate_id,))
        _execute(conn, "DELETE FROM exam_sessions WHERE candidate_id = ?", (candidate_id,))
        _execute(conn, "DELETE FROM candidates WHERE id = ?", (candidate_id,))


# ── Exam Session CRUD ──

def create_exam_session(candidate_id, track, time_limit_minutes=120):
    with get_connection() as conn:
        now = datetime.utcnow().isoformat()
        cur = _execute(conn,
            "INSERT INTO exam_sessions (candidate_id, track, status, time_limit_minutes, started_at) VALUES (?, ?, 'in_progress', ?, ?)" + (" RETURNING id" if USE_PG else ""),
            (candidate_id, track, time_limit_minutes, now))
        return _lastrowid(conn, cur)


def finish_exam_session(session_id, total_score, max_score, score_breakdown):
    with get_connection() as conn:
        now = datetime.utcnow().isoformat()
        _execute(conn,
            "UPDATE exam_sessions SET status = 'completed', finished_at = ?, total_score = ?, max_score = ?, score_breakdown = ? WHERE id = ?",
            (now, total_score, max_score, json.dumps(score_breakdown, ensure_ascii=False), session_id))


def update_exam_progress(session_id, current_question_index, answers_dict):
    """Save exam progress to DB for session recovery."""
    with get_connection() as conn:
        _execute(conn,
            "UPDATE exam_sessions SET current_question_index = ?, answers_json = ? WHERE id = ?",
            (current_question_index, json.dumps(answers_dict, ensure_ascii=False), session_id))


def get_exam_sessions(candidate_id=None):
    with get_connection() as conn:
        if candidate_id:
            cur = _execute(conn, "SELECT * FROM exam_sessions WHERE candidate_id = ? ORDER BY created_at DESC", (candidate_id,))
        else:
            cur = _execute(conn, "SELECT * FROM exam_sessions ORDER BY created_at DESC")
        return _fetchall(cur)


def get_exam_session(session_id):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM exam_sessions WHERE id = ?", (session_id,))
        return _fetchone(cur)


def get_active_exam_session(candidate_id):
    """Get in-progress exam session for a candidate (for session recovery)."""
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM exam_sessions WHERE candidate_id = ? AND status = 'in_progress' ORDER BY created_at DESC", (candidate_id,))
        return _fetchone(cur)


# ── Answer CRUD ──

def save_answer(session_id, question_id, response, is_correct, score, max_score, grading_notes=""):
    with get_connection() as conn:
        if USE_PG:
            _execute(conn,
                """INSERT INTO answers (session_id, question_id, response, is_correct, score, max_score, grading_notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (session_id, question_id) DO UPDATE SET
                       response = EXCLUDED.response, is_correct = EXCLUDED.is_correct,
                       score = EXCLUDED.score, grading_notes = EXCLUDED.grading_notes""",
                (session_id, question_id, response, is_correct, score, max_score, grading_notes))
        else:
            _execute(conn,
                """INSERT OR REPLACE INTO answers
                   (session_id, question_id, response, is_correct, score, max_score, grading_notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, question_id, response, is_correct, score, max_score, grading_notes))


def get_answers(session_id):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM answers WHERE session_id = ? ORDER BY id", (session_id,))
        return _fetchall(cur)


# ── Question Stats ──

def update_question_stats(question_id, is_correct, score):
    with get_connection() as conn:
        if USE_PG:
            _execute(conn,
                """INSERT INTO question_stats (question_id, times_shown, times_correct, avg_score)
                   VALUES (%s, 1, %s, %s)
                   ON CONFLICT(question_id) DO UPDATE SET
                       times_shown = question_stats.times_shown + 1,
                       times_correct = question_stats.times_correct + %s,
                       avg_score = (question_stats.avg_score * (question_stats.times_shown - 1) + %s) / question_stats.times_shown""",
                (question_id, int(is_correct), score, int(is_correct), score))
        else:
            _execute(conn,
                """INSERT INTO question_stats (question_id, times_shown, times_correct, avg_score)
                   VALUES (?, 1, ?, ?)
                   ON CONFLICT(question_id) DO UPDATE SET
                       times_shown = times_shown + 1,
                       times_correct = times_correct + ?,
                       avg_score = (avg_score * (times_shown - 1) + ?) / times_shown""",
                (question_id, int(is_correct), score, int(is_correct), score))


# ── Audit Log ──

def log_audit(action, user_id=None, resource_type=None, resource_id=None, details=None, ip_address=None):
    with get_connection() as conn:
        _execute(conn,
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, resource_type, resource_id, json.dumps(details, ensure_ascii=False) if details else None, ip_address))


def get_audit_log(limit=100):
    with get_connection() as conn:
        cur = _execute(conn, "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        return _fetchall(cur)
