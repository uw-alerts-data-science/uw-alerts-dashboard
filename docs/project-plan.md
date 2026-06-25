# UW Alerts Dashboard — Project Plan

> Produced: 2026-06-25. Target launch: mid-August 2026.

---

## Product Vision

A public civic tool and portfolio piece. Two distinct modes:

- **Live view** — situational awareness. Someone hears about an incident, opens the site, sees where it is and gets an update. Fast, clear, minimal friction.
- **Analytics view** — historical exploration. Tableau-style dashboard with a filterable map, linked charts, and external data overlays that update dynamically as filters change.

**Public URL target:** `uwalerts.live`

**Primary audience:** UW Seattle students, residents, and anyone near campus.

---

## Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js + MapLibre GL + Recharts | Replaces Flask + Folium |
| Backend API | FastAPI | Replaces Flask |
| Database | PostgreSQL 15 | Unchanged |
| Scraper | Python + Claude tool-use | Unchanged — stable, not being modified |
| Design | Figma | Design phase only |
| Infrastructure | DigitalOcean Kubernetes (DOKS) | ~$27/mo |

**Data freshness:** 15-minute polling with a visible last-updated timestamp. No websockets for v1.

---

## Team & Ownership

| Person | Role | Owns |
|---|---|---|
| Evan | PM + Architect | Notion board, weekly standup, K8s cluster provisioning, infra guidance, PR reviews |
| Engineer (friend) | Full-stack | FastAPI rewrite, Next.js frontend, K8s manifests for his services |
| DS 1 + DS 2 | Data science | Data exploration, visual specs, external dataset proposals, dbt (stretch), MCP server (stretch) |
| Designer (wife) | UX Design — phase 1 only | Figma mockups for 2 core views + component inventory |

**PM boundary:** Evan owns all project coordination. The team executes and reports blockers.

---

## The Two Core Views

### Live Alert View
- Dominant map of UW / U-District (MapLibre GL)
- Active alert markers with clean tooltips: incident type, time, address
- Status indicator: active alert count + last-updated timestamp
- Sidebar or bottom drawer: list view of current alerts

### Analytics Dashboard View
- Filterable map (date range, category, location radius)
- Linked charts that update as map filters change
- Stat widgets: total incidents, most common type, hottest area
- Time-series chart: incidents over time
- Category breakdown: bar or donut
- External data overlays (income, rent, Seattle Open Data — see DS scope below)

*Exact chart selection is owned by the DS folks via written specs in `docs/specs/`.*

---

## Data Science Scope

Four bodies of work, sequenced:

### 1. Data Exploration & Documentation
- Understand the existing schema: `incidents`, `alerts`, geocoding coverage, category distribution, time patterns
- Document findings as markdown in `docs/specs/`

### 2. Visual Specs
One markdown doc per proposed visualization committed to `docs/specs/`:
- The question it answers
- The SQL query that powers it
- Description of the visual: chart type, axes, filters
- The data shape the frontend needs
- Why it's interesting

### 3. External Dataset Proposals
One markdown doc per proposed dataset committed to `docs/specs/`:
- What it is and where it comes from
- How it joins to the incidents data
- What analytical question it unlocks
- Estimated ingestion complexity

**Candidate sources:**
- Seattle Open Data Portal — 911 calls, Seattle PD incidents, 311 complaints
- Census / ACS — income, demographics, housing cost burden by tract
- UW academic calendar — quarter boundaries (incident patterns likely correlate)
- King County Assessor — property values, parcel data
- OpenStreetMap — amenities, bars, ATMs, parking (environmental context)
- Zillow / rental data — rent prices by area
- GTFS / King County Metro — transit stops and frequency

### 4. Stretch Goals
- **dbt** — productionize SQL transformations with version control, docs, and tests
- **MCP server** — expose the incidents database as Claude tools
- **Natural language query interface** — built on top of the MCP server

---

## Build Sequence

### Phase 0 — Design + Exploration (parallel)
- Designer: Figma mockups for both core views + component inventory (~10 key components)
- DS folks: data exploration, first visual specs committed to `docs/specs/`

### Phase 1 — Thin Vertical Slice (target: end of July 2026)
Get one feature fully working end-to-end in production:

1. FastAPI endpoint for live alerts (`GET /alerts/live`)
2. Next.js map view consuming it — MapLibre GL, real Postgres data, markers + tooltips
3. Deployed to DOKS at `uwalerts.live`

This is the spine. Everything else hangs off it.

### Phase 2 — Analytics Dashboard (target: mid-August 2026)
- Historical filtering (date range, category, location)
- Recharts dashboard: time-series, category breakdown, stat widgets
- External dataset integrations (DS-specced and validated)

### Phase 3 — Stretch (post-August 2026)
- dbt transformation layer
- MCP server + natural language query interface
- Kubernetes CronJob manifest for scraper (it's designed for this — just needs the manifest)

---

## Infrastructure

| Responsibility | Owner |
|---|---|
| DOKS cluster provisioning | Evan |
| Ingress, DNS, TLS (cert-manager) | Evan |
| Secrets management | Evan |
| FastAPI + Next.js K8s manifests (Deployments, Services, ConfigMaps) | Engineer |
| Scraper CronJob manifest | DS folks |
| Domain registration (`uwalerts.live`) | Engineer (when v1 is close) |

---

## Coordination

- **Weekly standup** — Evan runs it
- **Notion board** — Evan builds and owns; team executes against it
- **Written specs** — DS folks commit markdown docs to `docs/specs/` for all data and visualization proposals
- **PRs** — Evan reviews as technical guide; all work merges via PR to `main`
- **Git workflow** — conventional commits + typed branch names + worktrees (see README)

---

## Open Items at Project Start

From the existing `feat-agentic-scraper` branch:

- [ ] Commit the `test_migrate.py` count fix (small — `alerts_inserted` 285→265, `duplicates_skipped` 0→20)
- [ ] Decide fate of `/update_map` legacy route and `parse_uw_alerts/` module (depends on OpenAI + CSV)
- [ ] Geocoding backfill for null-lat incidents — no workflow exists yet (DS scope)
- [ ] Update `CLAUDE.md` — still says OpenAI; actual scraper uses Anthropic/Claude
- [ ] Provision DOKS cluster
- [ ] Register `uwalerts.live`
