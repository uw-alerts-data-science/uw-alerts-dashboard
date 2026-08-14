CREATE TABLE IF NOT EXISTS incidents (
    id                SERIAL PRIMARY KEY,
    category          VARCHAR(255),
    nearest_address   TEXT,
    google_address    TEXT,
    lat               DECIMAL(10, 7),
    lng               DECIMAL(10, 7),
    occurred_at       TIMESTAMPTZ,
    first_reported_at TIMESTAMPTZ,
    last_updated_at   TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    -- SHA-256 of the raw article text as of the last successful live-agent
    -- scrape. Populated directly by Python (never by the LLM), so the live
    -- agent can skip calling Claude entirely when a known article's current
    -- text is unchanged, without depending on the LLM faithfully
    -- reproducing every Unicode character when it "copies" text verbatim.
    last_scraped_hash CHAR(64)
);

-- Idempotent forward-migration for databases created before this column
-- existed (CREATE TABLE IF NOT EXISTS above only applies to brand-new tables).
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS last_scraped_hash CHAR(64);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS status VARCHAR(20);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS num_suspects INT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS weapon VARCHAR(50);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS suspect_at_large BOOLEAN;

CREATE TABLE IF NOT EXISTS alerts (
    id               SERIAL PRIMARY KEY,
    incident_id      INT REFERENCES incidents(id) ON DELETE CASCADE,
    alert_type       VARCHAR(50) CHECK (alert_type IN ('original', 'update')),
    reported_at      TIMESTAMPTZ,
    incident_time    TIMESTAMPTZ,
    summary          TEXT,
    full_text        TEXT NOT NULL,
    raw_scraped_text TEXT,
    source_url       VARCHAR(500),
    text_hash        CHAR(64) NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_text_hash ON alerts(text_hash);
CREATE INDEX IF NOT EXISTS idx_incidents_reported   ON incidents(first_reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_category   ON incidents(category);
CREATE INDEX IF NOT EXISTS idx_incidents_location   ON incidents(lat, lng);
CREATE INDEX IF NOT EXISTS idx_alerts_incident      ON alerts(incident_id);
