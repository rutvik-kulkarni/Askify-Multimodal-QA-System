-- ============================================================
-- Askify - Supabase Database Schema
-- Run this entire file in your Supabase SQL Editor:
-- https://supabase.com/dashboard -> Project -> SQL Editor -> New Query
-- ============================================================

-- Table 1: Chat sessions (one per analyzed video/content)
CREATE TABLE IF NOT EXISTS askify_sessions (
    session_id      TEXT PRIMARY KEY,
    label           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    content_snippet TEXT,
    source          TEXT
);

-- Table 2: Individual Q&A messages within a session
CREATE TABLE IF NOT EXISTS askify_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT REFERENCES askify_sessions(session_id) ON DELETE CASCADE,
    question    TEXT,
    answer      TEXT,
    timestamp   TIMESTAMPTZ DEFAULT NOW()
);

-- Table 3: User learning progress (streak, topics, etc.)
CREATE TABLE IF NOT EXISTS askify_progress (
    date              DATE PRIMARY KEY DEFAULT CURRENT_DATE,
    questions_asked   INT DEFAULT 0,
    topics_seen       TEXT[] DEFAULT '{}'
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_messages_session ON askify_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON askify_sessions(created_at DESC);
