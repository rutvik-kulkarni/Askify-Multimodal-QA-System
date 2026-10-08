"""
advanced_features.py — Optional personalization & recommendation features for Askify.

This file is OPTIONAL. If you delete it, the core app (test4.py) still works perfectly.
It adds:
  - Topic tagging for each Q&A session
  - "Related Questions" suggestions based on transcript
  - Learning progress tracker (topics covered per session)
  - Smart follow-up question generator
  - Weekly study streak tracking
"""

import json
import os
import re
from datetime import datetime, date
from collections import Counter

try:
    from supabase import create_client as _sb_create
    _SB_URL = os.getenv("SUPABASE_URL", "").strip().strip('"')
    _SB_KEY = os.getenv("SUPABASE_KEY", "").strip().strip('"')
    _sb_client = _sb_create(_SB_URL, _SB_KEY) if (_SB_URL and _SB_URL != "YOUR_SUPABASE_URL_HERE") else None
except Exception:
    _sb_client = None

try:
    import streamlit as st
    _STREAMLIT_AVAILABLE = True
except ImportError:
    _STREAMLIT_AVAILABLE = False

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "askify_progress.json")

# ─────────────────────────────────────────────────────────
# Topic Extraction (lightweight, no extra dependencies)
# ─────────────────────────────────────────────────────────

STOP_WORDS = {
    "the","a","an","is","are","was","were","be","been","being","have","has","had",
    "do","does","did","will","would","could","should","may","might","shall","can",
    "to","of","in","for","on","with","at","by","from","up","about","into","through",
    "this","that","these","those","it","its","they","them","their","we","our","you",
    "your","i","me","my","he","she","his","her","and","or","but","if","then","so",
    "not","no","what","how","when","where","who","which","there","here","just","also",
    "more","than","any","all","some","such","like","very","too","also","only","both",
    "each","few","more","most","other","same","than","then","too","very","just"
}


def extract_topics(text: str, top_n: int = 8) -> list:
    """Extract top keyword topics from transcript text."""
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    freq = Counter(filtered)
    return [word for word, _ in freq.most_common(top_n)]


def generate_followup_questions(transcript: str, asked_questions: list, groq_client, model: str) -> list:
    """
    Generate smart follow-up questions the user hasn't asked yet,
    based on transcript content.
    Returns a list of up to 4 question strings.
    """
    asked_str = "\n".join(f"- {q}" for q in asked_questions[-5:]) if asked_questions else "None yet"
    snippet = transcript[:2000]
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "You are an educational assistant. Generate 4 insightful follow-up questions "
                    "a student should ask about this content. The questions should not repeat the "
                    "already-asked questions. Return ONLY a numbered list, one question per line."
                )},
                {"role": "user", "content": (
                    f"Content excerpt:\n{snippet}\n\n"
                    f"Already asked:\n{asked_str}\n\n"
                    "Generate 4 new follow-up questions:"
                )}
            ],
            max_tokens=300
        )
        raw = response.choices[0].message.content.strip()
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        questions = []
        for line in lines:
            # Strip leading numbering like "1." or "1)"
            clean = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if clean and "?" in clean:
                questions.append(clean)
        return questions[:4]
    except Exception:
        return []


def generate_summary_points(transcript: str, groq_client, model: str) -> list:
    """
    Generate 5 key learning points from the transcript.
    Returns a list of strings.
    """
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "You are an expert educator. Extract 5 key learning points from the content. "
                    "Return ONLY a numbered list. Be concise (one sentence each)."
                )},
                {"role": "user", "content": f"Content:\n{transcript[:3000]}\n\nKey learning points:"}
            ],
            max_tokens=400
        )
        raw = response.choices[0].message.content.strip()
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        points = []
        for line in lines:
            clean = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if clean:
                points.append(clean)
        return points[:5]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────
# Learning Progress Tracker
# ─────────────────────────────────────────────────────────

def _load_progress() -> dict:
    """Load progress, preferring Supabase if available."""
    if _sb_client:
        try:
            today = date.today().isoformat()
            # Get last 30 days of records
            rows = _sb_client.table("askify_progress").select("*").order("date", desc=True).limit(30).execute().data or []
            sessions_by_date = {r["date"]: {"questions": r["questions_asked"]} for r in rows}
            all_topics = []
            for r in rows:
                all_topics.extend(r.get("topics_seen") or [])
            streak_dates = [r["date"] for r in rows]
            total_q = sum(r["questions_asked"] for r in rows)
            return {"sessions_by_date": sessions_by_date, "total_questions": total_q,
                    "topics_seen": list(set(all_topics)), "streak_dates": sorted(streak_dates)}
        except Exception as e:
            print(f"[advanced_features] Supabase load_progress error: {e}")
    # Local fallback
    if not os.path.exists(PROGRESS_FILE):
        return {"sessions_by_date": {}, "total_questions": 0, "topics_seen": [], "streak_dates": []}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sessions_by_date": {}, "total_questions": 0, "topics_seen": [], "streak_dates": []}


def _save_progress(data: dict):
    """Save is handled directly in record_activity for Supabase."""
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_activity(topics: list, questions_asked: int = 1):
    """Record that a user studied today and asked questions."""
    today = date.today().isoformat()
    if _sb_client:
        try:
            # Upsert today's row
            existing = _sb_client.table("askify_progress").select("*").eq("date", today).execute().data
            if existing:
                row = existing[0]
                merged_topics = list(set((row.get("topics_seen") or []) + topics))
                _sb_client.table("askify_progress").update({
                    "questions_asked": row["questions_asked"] + questions_asked,
                    "topics_seen": merged_topics
                }).eq("date", today).execute()
            else:
                _sb_client.table("askify_progress").insert({
                    "date": today,
                    "questions_asked": questions_asked,
                    "topics_seen": topics
                }).execute()
            return
        except Exception as e:
            print(f"[advanced_features] Supabase record_activity error: {e}")
    # Local fallback
    data = _load_progress()
    if today not in data["sessions_by_date"]:
        data["sessions_by_date"][today] = {"questions": 0, "topics": []}
    data["sessions_by_date"][today]["questions"] += questions_asked
    seen = set(data.get("topics_seen", []))
    for t in topics:
        seen.add(t)
    data["topics_seen"] = list(seen)
    data["total_questions"] = data.get("total_questions", 0) + questions_asked
    streak_dates = data.get("streak_dates", [])
    if today not in streak_dates:
        streak_dates.append(today)
    data["streak_dates"] = sorted(streak_dates)[-30:]
    _save_progress(data)


def get_streak() -> int:
    """Calculate current consecutive day streak."""
    data = _load_progress()
    streak_dates = sorted(data.get("streak_dates", []), reverse=True)
    if not streak_dates:
        return 0
    
    streak = 0
    current = date.today()
    for d_str in streak_dates:
        d = date.fromisoformat(d_str)
        diff = (current - d).days
        if diff == streak:
            streak += 1
        elif diff > streak:
            break
    return streak


def get_stats() -> dict:
    """Return summary stats for display."""
    data = _load_progress()
    return {
        "total_questions": data.get("total_questions", 0),
        "total_topics": len(data.get("topics_seen", [])),
        "streak": get_streak(),
        "days_active": len(data.get("sessions_by_date", {}))
    }


# ─────────────────────────────────────────────────────────
# Streamlit UI Components (called from test4.py)
# ─────────────────────────────────────────────────────────

def render_followup_suggestions(transcript: str, asked_questions: list, groq_client, model: str):
    """Render a 'Suggested Questions' panel in the app."""
    if not _STREAMLIT_AVAILABLE:
        return
    
    with st.expander("💡 Suggested Follow-up Questions", expanded=False):
        if st.button("🔄 Generate Suggestions", key="gen_suggestions"):
            with st.spinner("Thinking of good questions for you..."):
                suggestions = generate_followup_questions(transcript, asked_questions, groq_client, model)
            if suggestions:
                st.session_state["_af_suggestions"] = suggestions
            else:
                st.warning("Could not generate suggestions. Try again.")
        
        suggestions = st.session_state.get("_af_suggestions", [])
        if suggestions:
            st.markdown("**Click a question to use it:**")
            for i, q in enumerate(suggestions):
                if st.button(f"❓ {q}", key=f"sugg_{i}", use_container_width=True):
                    st.session_state.user_question = q
                    st.rerun()


def render_key_points(transcript: str, groq_client, model: str):
    """Render a 'Key Learning Points' panel."""
    if not _STREAMLIT_AVAILABLE:
        return
    
    with st.expander("📌 Key Learning Points", expanded=False):
        if st.button("📖 Extract Key Points", key="extract_kp"):
            with st.spinner("Extracting key insights..."):
                points = generate_summary_points(transcript, groq_client, model)
            if points:
                st.session_state["_af_key_points"] = points
            else:
                st.warning("Could not extract key points.")
        
        points = st.session_state.get("_af_key_points", [])
        if points:
            for i, point in enumerate(points, 1):
                st.markdown(f"""
                <div style="background:#f0f9ff; border-left:3px solid #0ea5e9; 
                            padding:10px 14px; border-radius:8px; margin:6px 0;
                            color:#0c4a6e; font-size:0.95rem;">
                    <strong>{i}.</strong> {point}
                </div>
                """, unsafe_allow_html=True)


def render_topic_tags(transcript: str):
    """Render extracted topic tags for the current content."""
    if not _STREAMLIT_AVAILABLE:
        return
    
    topics = extract_topics(transcript)
    if topics:
        tags_html = "".join([
            f'<span style="background:#e0f2fe; color:#0369a1; padding:4px 12px; '
            f'border-radius:20px; font-size:0.8rem; margin:3px; display:inline-block; '
            f'font-weight:600;">{t}</span>'
            for t in topics
        ])
        st.markdown(f"""
        <div style="margin: 8px 0 16px 0;">
            <span style="font-size:0.85rem; color:#64748b; font-weight:600;">🏷️ Topics: </span>
            {tags_html}
        </div>
        """, unsafe_allow_html=True)


def render_progress_sidebar():
    """Render learning stats in the sidebar."""
    if not _STREAMLIT_AVAILABLE:
        return
    
    stats = get_stats()
    st.markdown("---")
    st.markdown("### 📈 Your Progress")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🔥 Streak", f"{stats['streak']}d")
        st.metric("❓ Questions", stats['total_questions'])
    with col2:
        st.metric("📅 Days Active", stats['days_active'])
        st.metric("🏷️ Topics", stats['total_topics'])
