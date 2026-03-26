-- init_db.sql — Bootstrap PostgreSQL for Ginie + Canton
--
-- Docker: mounted into /docker-entrypoint-initdb.d/ and runs automatically.
-- Manual: psql -U postgres -f backend/scripts/init_db.sql
--
-- TWO separate databases:
--   1. ginie_daml      — Ginie application state (jobs, parties, sessions)
--   2. canton_sandbox   — Canton participant node internal storage
--
-- Canton manages its own schema; we never write to canton_sandbox.
-- Ginie tables below are also created by SQLAlchemy on startup,
-- so this SQL is a safety net / reference.

-- ============================================================
-- Create databases via shell script instead (see init_databases.sh)
-- Docker entrypoint uses /docker-entrypoint-initdb.d/*.sh for this.
-- This file creates tables in whichever DB it's connected to.
-- ============================================================

CREATE TABLE IF NOT EXISTS registered_parties (
    id              SERIAL PRIMARY KEY,
    party_id        TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    public_key_fp   TEXT,
    canton_env      TEXT NOT NULL DEFAULT 'sandbox',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL UNIQUE,
    party_id        TEXT NOT NULL REFERENCES registered_parties(party_id),
    jwt_token       TEXT NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_history (
    id              SERIAL PRIMARY KEY,
    job_id          TEXT NOT NULL UNIQUE,
    party_id        TEXT,
    prompt          TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    current_step    TEXT NOT NULL DEFAULT 'idle',
    progress        INT NOT NULL DEFAULT 0,
    canton_env      TEXT NOT NULL DEFAULT 'sandbox',
    result_json     JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deployed_contracts (
    id              SERIAL PRIMARY KEY,
    contract_id     TEXT NOT NULL,
    package_id      TEXT NOT NULL DEFAULT '',
    template_id     TEXT NOT NULL DEFAULT '',
    job_id          TEXT REFERENCES job_history(job_id),
    party_id        TEXT,
    dar_path        TEXT,
    canton_env      TEXT NOT NULL DEFAULT 'sandbox',
    explorer_link   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_history_status ON job_history(status);
CREATE INDEX IF NOT EXISTS idx_job_history_party ON job_history(party_id);
CREATE INDEX IF NOT EXISTS idx_deployed_contracts_job ON deployed_contracts(job_id);
CREATE INDEX IF NOT EXISTS idx_deployed_contracts_party ON deployed_contracts(party_id);

-- Done
SELECT 'Ginie databases initialized successfully' AS status;
