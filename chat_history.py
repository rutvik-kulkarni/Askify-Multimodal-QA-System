"""
chat_history.py — Supabase-backed chat history manager for Askify.

Stores Q&A sessions and messages in Supabase.
Falls back to local JSON if Supabase is not configured.
"""

import os
import hashlib
import json
from datetime import datetime

# ── Supabase Client Setup ──────────────────────────────────────────────────────
_client = None
_USE_SUPABASE = False

def _get_client():
    global _client, _USE_SUPABASE
    if _client is not None:
        return _client
    try:
        url = os.getenv("SUPABASE_URL", "").strip().strip('"')
        key = os.getenv("SUPABASE_KEY", "").strip().strip('"')
        if url and key and url != "YOUR_SUPABASE_URL_HERE" and key != "YOUR_SUPABASE_ANON_KEY_HERE":
            from supabase import create_client
            _client = create_client(url, key)
            _USE_SUPABASE = True
            return _client
    except Exception as e:
        print(f"[chat_history] Supabase init failed, using local JSON: {e}")
    return None


# ── Local JSON Fallback ────────────────────────────────────────────────────────
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "askify_history.json")

def _local_load() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _local_save(data: dict):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Public API ─────────────────────────────────────────────────────────────────

def make_session_id(content_key: str, label: str = "") -> str:
    """Create a unique, stable session ID."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = hashlib.md5(content_key.encode()).hexdigest()[:6]
    name = label.strip()[:30] if label else content_key[:20]
    return f"{ts}_{short}_{name}".replace(" ", "_")


def create_session(session_id: str, label: str, source: str, content_snippet: str) -> dict:
    """Create and persist a new session."""
    session = {
        "session_id": session_id,
        "label": label,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content_snippet": content_snippet[:200],
        "source": source,
        "messages": []
    }
    client = _get_client()
    if client:
        try:
            client.table("askify_sessions").upsert({
                "session_id": session_id,
                "label": label,
                "content_snippet": content_snippet[:200],
                "source": source
            }).execute()
            return session
        except Exception as e:
            print(f"[chat_history] Supabase create_session error: {e}")
    # Fallback to local
    data = _local_load()
    data[session_id] = session
    _local_save(data)
    return session


def add_message(session_id: str, question: str, answer: str):
    """Append a Q&A pair to a session."""
    client = _get_client()
    if client:
        try:
            client.table("askify_messages").insert({
                "session_id": session_id,
                "question": question,
                "answer": answer
            }).execute()
            return
        except Exception as e:
            print(f"[chat_history] Supabase add_message error: {e}")
    # Fallback to local
    data = _local_load()
    if session_id not in data:
        return
    data[session_id].setdefault("messages", []).append({
        "timestamp": datetime.now().strftime("%H:%M"),
        "question": question,
        "answer": answer
    })
    _local_save(data)


def get_session(session_id: str) -> dict:
    """Return a session with all its messages."""
    client = _get_client()
    if client:
        try:
            session_resp = client.table("askify_sessions").select("*").eq("session_id", session_id).execute()
            msg_resp = client.table("askify_messages").select("*").eq("session_id", session_id).order("timestamp").execute()
            if session_resp.data:
                s = session_resp.data[0]
                s["messages"] = [
                    {"timestamp": m["timestamp"], "question": m["question"], "answer": m["answer"]}
                    for m in (msg_resp.data or [])
                ]
                return s
        except Exception as e:
            print(f"[chat_history] Supabase get_session error: {e}")
    # Fallback to local
    data = _local_load()
    return data.get(session_id, {"session_id": session_id, "label": "", "messages": []})


def get_sessions_sorted() -> list:
    """Return all sessions newest first, with messages included."""
    client = _get_client()
    if client:
        try:
            session_resp = client.table("askify_sessions").select("*").order("created_at", desc=True).execute()
            sessions = session_resp.data or []
            # Attach messages to each session
            for s in sessions:
                msg_resp = client.table("askify_messages").select("*").eq("session_id", s["session_id"]).order("timestamp").execute()
                s["messages"] = [
                    {"timestamp": m["timestamp"], "question": m["question"], "answer": m["answer"]}
                    for m in (msg_resp.data or [])
                ]
            return sessions
        except Exception as e:
            print(f"[chat_history] Supabase get_sessions_sorted error: {e}")
    # Fallback to local
    data = _local_load()
    sessions = list(data.values())
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return sessions


def delete_session(session_id: str):
    """Delete a session and its messages."""
    client = _get_client()
    if client:
        try:
            # Messages cascade delete because of FK constraint in schema
            client.table("askify_sessions").delete().eq("session_id", session_id).execute()
            return
        except Exception as e:
            print(f"[chat_history] Supabase delete_session error: {e}")
    # Fallback to local
    data = _local_load()
    if session_id in data:
        del data[session_id]
        _local_save(data)


def rename_session(session_id: str, new_label: str):
    """Rename a session's label."""
    client = _get_client()
    if client:
        try:
            client.table("askify_sessions").update({"label": new_label}).eq("session_id", session_id).execute()
            return
        except Exception as e:
            print(f"[chat_history] Supabase rename_session error: {e}")
    # Fallback to local
    data = _local_load()
    if session_id in data:
        data[session_id]["label"] = new_label
        _local_save(data)
