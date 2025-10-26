# CollabNet – Collaborator Finder Platform

CollabNet is a full-stack prototype that helps researchers discover potential collaborators by combining live OpenAlex data with curated analytics. The React frontend surfaces trends, search tools, and compatibility insights, while the Flask backend orchestrates API calls, computes proactive metrics, and falls back to an offline corpus when the network is unreachable.

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [Launching the Backend](#launching-the-backend)
  - [Launching the Frontend](#launching-the-frontend)
- [Data Flow Walkthrough](#data-flow-walkthrough)
  - [Dashboard Visualisations](#dashboard-visualisations)
  - [Search and Researcher Drill-Down](#search-and-researcher-drill-down)
  - [Match Evaluation & Compatibility Report](#match-evaluation--compatibility-report)
- [Backend Capabilities](#backend-capabilities)
  - [Trending Analytics](#trending-analytics)
  - [Compatibility Scoring Model](#compatibility-scoring-model)
  - [Fallback & Resilience Layer](#fallback--resilience-layer)
  - [REST Endpoints](#rest-endpoints)
- [Offline Dataset](#offline-dataset)
- [Extending the Project](#extending-the-project)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
frontend/ (React + Tailwind + Chart.js)
├── src/pages
│   ├── Dashboard.jsx         ← Trend visualisations & quick search
│   ├── SearchResults.jsx     ← Topic/author search with co-author graph previews
│   ├── MatchEvaluating.jsx   ← Spinner that triggers /api/match
│   └── Compatibility.jsx     ← Gauge, bar chart & evidence lists
└── public/

backend/ (Flask)
├── app.py                    ← REST API, OpenAlex integrations, analytics
└── openalex_offline.py       ← Offline sample corpus & helper lookups
```

- **Frontend**: React (React Router, Chart.js, Leaflet, React Force Graph). It proxies API calls to the backend (`package.json` sets `"proxy": "http://localhost:5000"`).
- **Backend**: Flask app that wraps OpenAlex endpoints, aggregates data, and performs analytics (trending topics/researchers, compatibility scoring, co-author graphs). Uses `requests` with custom retry logic and resilient fallbacks.
- **Offline data**: Rich sample dataset in `openalex_offline.py` to keep the UI functional without network access.

---

## Prerequisites

- **Python**: 3.11+ recommended (the repo ships with a sample `venv/` but you can create your own).
- **Node.js**: 18.x (React Scripts 5 requires ≥ Node 14; Node 18 LTS tested).
- **npm**: matches Node installation.
- **OpenAlex connectivity**: Optional, but required for live data. When unavailable, the backend automatically falls back to offline samples.

---

## Quick Start

### Launching the Backend

```bash
cd backend
python -m venv .venv               # optional – create your own virtualenv
.\.venv\Scripts\activate           # Windows
# source .venv/bin/activate        # macOS / Linux
pip install -r requirements.txt
python app.py
```

By default the Flask app runs on `http://0.0.0.0:5000` with debug logging enabled. The only external dependency is OpenAlex, accessed via HTTPS with the `collab-finder@example.com` mailto parameter.

### Launching the Frontend

```bash
cd frontend
npm install
npm start
```

The development server starts at `http://localhost:3000` and transparently proxies API requests to the Flask backend.

---

## Data Flow Walkthrough

### Dashboard Visualisations

File: `frontend/src/pages/Dashboard.jsx`

1. **Trending fetch** – On mount, issues parallel requests to:
   - `/api/trending/topics` → returns topics with recent publication surges.
   - `/api/trending/scientists` → returns authors with high recent activity.
2. **Institution aggregation** – For each trending topic, fetches `/api/institutions/<topic>` to pull institutional attribution counts, merges them, and keeps the top five earners by works.
3. **Network sizing** – For each trending scientist, calls `/api/coauthor-network/author/<id>` and inspects `payload.stats.node_count` to quantify the breadth of their co-author graph.
4. **Charts**:
   - **Trending Topics (bar)** – labels = concept display names, values = total `works_count` (global tally) for scale context.
   - **Top Institutions (bar)** – labels = institution names, values = aggregated works totals from the previous step.
   - **Network Momentum (line)** – labels = trending researcher names; values = node counts from their co-author networks.
5. **Overlay** – Submitting an empty search toggles an overlay panel that showcases the same trending data the user sees in the charts, encouraging exploration.

### Search and Researcher Drill-Down

File: `frontend/src/pages/SearchResults.jsx`

- **Topic mode**: `/api/topics?query=<q>` fetches matching concepts, the first concept is selected, and `/api/authors/<concept>` fetches leading authors. All cards display works, citations, and last-known institutions.
- **Author mode**: `/api/authors?query=<q>` returns matching authors outright.
- Selecting an author triggers two follow-up calls:
  - `/api/author/<id>` for enriched profile data if summary stats were missing.
  - `/api/coauthor-network/author/<id>` to render a Force-Directed collaboration network (nodes = authors, weight = shared works).

### Match Evaluation & Compatibility Report

Files: `frontend/src/pages/MatchEvaluating.jsx`, `frontend/src/pages/Compatibility.jsx`

1. Match flow begins on `/match-evaluating?target=<id>&name=<display>`:
   - Displays a progress indicator.
   - POSTs `{ "target_id": "<OpenAlex Author ID>" }` to `/api/match`.
2. `/api/match` aggregates detailed profiles and returns:
   - `breakdown`: overall score and sub-metrics on a 0–100 scale.
   - `evidence`: overlapping concepts, mutual co-authors, aligned publications, and median publication years.
3. Compatibility page renders:
   - **Gauge** – overall percentage from `breakdown.overall` using Chart.js Doughnut.
   - **Horizontal Bar Chart** – sub-metrics (topic similarity, co-author distance, institution proximity, recency alignment).
   - **Evidence Lists** – bullet lists for overlapping concepts, shared co-authors, and a list of aligned publications `{ title, year }` plus context about publication recency alignment.

---

## Backend Capabilities

### Trending Analytics

Implementation: `backend/app.py` (`compute_trending_topics`, `compute_trending_scientists`)

1. **Time windows** – Uses a rolling six-month window (`TRENDING_WINDOW_MONTHS = 6`). Dates are computed on the fly with `trending_window_strings()`:
   - Recent window: `[recent_start, today]`
   - Previous window: prior six months ending the day before `recent_start`
2. **OpenAlex groupings**:
   - `/works?group_by=concepts.id` for topics.
   - `/works?group_by=authorships.author.id` for scientists.
   Both calls request up to `limit * 4` entries to ensure enough candidates before filtering.
3. **Growth computation**:
   - `recent_count` = works in recent window.
   - `previous_count` = works in previous window (default 0 if absent).
   - `growth` = `recent_count - previous_count`.
   - `growth_rate` = `(recent - previous) / (previous or recent)` for tie-breaking.
4. **Ranking**:
   - Topics prefer positive growth. The ranking tuple is `(growth, growth_rate, recent_count)` descending.
   - Scientists sort by `(recent_count, growth)` descending before enrichment.
5. **Enrichment**:
   - Concepts → `fetch_concept_brief` hits `/concepts/<id>` (parallelised with `ThreadPoolExecutor`).
   - Authors → `fetch_author_brief` hits `/authors/<id>` for `works_count`, `cited_by_count`, and institution metadata.
6. **Return payload**:
   ```json
   {
     "topics": [{
       "id": "https://openalex.org/T101",
       "display_name": "Machine Learning",
       "description": "...",
       "works_count": 2450000,
       "recent_publications": 18450,
       "growth": 3220
     }],
     "scientists": [{
       "id": "https://openalex.org/A1969205032",
       "display_name": "Fei-Fei Li",
       "works_count": 420,
       "cited_by_count": 98000,
       "last_known_institution": {...},
       "recent_publications": 28,
       "growth": 9
     }]
   }
   ```
7. **Fallback** – If any upstream call fails, the endpoint supplies offline equivalents (`OFFLINE_DATA.trending_topics`, `OFFLINE_DATA.trending_scientists`).

### Compatibility Scoring Model

Implementation: `backend/app.py` (`compute_compatibility` and helpers)

**Profile construction**
- `collect_research_profile(author_id)` builds a profile by combining:
  - Summary stats (`fetch_author_brief` → `/authors/<id>`).
  - Works (`fetch_author_works` → `/works` filtered by author, newest first, up to 200 entries).
  - Fallbacks to the offline corpus for both metadata and works when necessary.
- `build_research_profile` extracts:
  - `concept_counts`: weighted sum of concept scores across the author’s works.
  - `concept_names`: display names for reporting.
  - `coauthors`: mapping of collaborator ID → display name.
  - `coauthor_graph`: adjacency set for BFS pathfinding.
  - `works`: curated work summaries for evidence (title, year, concepts, authors, citations).
  - `median_year`: median publication year (rounded).
  - `institution`: normalized institution object (`id`, `display_name`, `type`, `country_code`).

**Metrics**
1. **Topic Similarity (40%)**
   - Converts concept frequency dictionaries into sparse vectors.
   - Cosine similarity = `dot(A, B) / (||A|| * ||B||)`.
   - Scaled to 0–100 by multiplying by 100 and clamping.
   - Evidence: top five overlapping concepts with relative weights, e.g.
     `Machine Learning (you 12.50 · them 10.80)`.
2. **Co-author Distance (30%)**
   - Merges user and target co-author graphs.
   - Shortest path computed with BFS (up to depth 6).
   - Score mapping:
     | Path length | Score |
     |-------------|-------|
     | 0 (same person) | 100 |
     | 1 (direct co-author) | 100 |
     | 2 | 80 |
     | 3 | 55 |
     | 4 | 35 |
     | ≥5 or unknown | 15 (or 0 if disconnected) |
   - Evidence: list of mutual co-author names (up to five).
3. **Institution Proximity (20%)**
   - Hierarchical comparison:
     - Same `institution.id` → 100.
     - Same `country_code` → 80.
     - Same `type` (e.g., education, business) → 60.
     - Both institutions present but otherwise different → 40.
     - Missing data → 0.
4. **Recency Alignment (10%)**
   - Uses median publication year for user (`y_u`) and target (`y_t`).
   - Score = `max(0, 100 - 12.5 * |y_u - y_t|)` (every year difference costs 12.5 points).
   - Evidence includes both medians for context, even when missing.

**Overall Score**
```
overall = round(
    0.40 * topic_similarity +
    0.30 * coauthor_distance +
    0.20 * institution_proximity +
    0.10 * recency_alignment
)
```
Clamped to `[0, 100]`. All sub-metrics are stored in `breakdown` for display on the compatibility page.

**Aligned Publications**
- Filters target works to those containing overlapping concept IDs (top 10 overlaps).
- Returns up to five entries sorted by publication year (newest first).
- Each entry includes `title`, `year`, and the matched concepts.

### Fallback & Resilience Layer

- All OpenAlex helper functions (`fetch_openalex`, `fetch_author_endpoint`, `fetch_works_endpoint`, `fetch_institution_endpoint`) catch `requests.RequestException`, log details, and return `None` to indicate failure.
- Endpoint handlers interpret `None` as “switch to offline data”:
  - Search endpoints use `OFFLINE_DATA.search_topics/search_authors`.
  - Trending endpoints use curated trending lists.
  - Compatibility uses `OFFLINE_DATA.author_profile` + `author_works` to rebuild complete profiles offline.
- Offline detections ensure responses always contain arrays/objects (never `null`), so the frontend can render consistent placeholders.

### REST Endpoints

| Method | Route | Description | Key Params |
|--------|-------|-------------|------------|
| GET | `/api/health` | Simple ok check | – |
| GET | `/api/topics` | Search OpenAlex concepts | `q` (or `query`), `limit` |
| GET | `/api/authors` | Search OpenAlex authors by name | `q` (or `query`), `limit` |
| GET | `/api/authors/<topic_id>` | Authors associated with a concept | `limit` |
| GET | `/api/author/<author_id>` | Detailed author profile | – |
| GET | `/api/institutions/<topic_id>` | Institutions active in a concept | `limit` |
| GET | `/api/coauthor-network/<topic_id>` | Co-author graph seeded from works with a topic | `limit_works` (≤200) |
| GET | `/api/coauthor-network/author/<author_id>` | Author-centric co-author graph | `limit_works` (≤200) |
| GET | `/api/trending/topics` | Top topics by recent growth | `limit` (default 5, max 20) |
| GET | `/api/trending/scientists` | Top researchers by recent output | `limit` (default 5, max 20) |
| POST | `/api/match` | Compatibility analysis | JSON body `{ target_id, user_id? }` |

Sample compatibility request:
```bash
curl -X POST http://localhost:5000/api/match \
  -H "Content-Type: application/json" \
  -d '{"target_id": "https://openalex.org/A1969205032"}'
```

---

## Offline Dataset

Defined in `backend/openalex_offline.py`:

- Mimics OpenAlex payload shapes (topics, authors, institutions, networks).
- Includes curated trending metrics (`_trending_topics_data`, `_trending_scientists_data`) aligned with the UI’s expectations (`recent_publications`, `growth`, counts).
- Provides synthetic works per author (titles, years, concepts, co-authors) so compatibility scoring remains meaningful offline.
- Offers helper methods (`search_topics`, `author_profile`, `author_works`, `trending_topics`, etc.) consumed by the backend when real API calls fail.
- `default_user_id()` currently returns Fei-Fei Li’s OpenAlex ID, used when `/api/match` is called without a `user_id`.

---

## Extending the Project

- **Change user profile source**: Right now the backend assumes a default user ID until a dedicated user profile endpoint is introduced. Plugging in an authenticated profile would simply require replacing the `user_id` selection logic in `/api/match`.
- **Adjust weightings**: Tune the constants in `compute_compatibility` to emphasise different collaboration signals.
- **Add more metrics**: e.g., funding overlap, geographic proximity, research impact trajectory. Compute your metric, normalise to `[0, 100]`, and adjust the weighted average.
- **Persist results**: Introduce a database to store cached trending lists or previously computed compatibility scores for quicker access.
- **Broaden offline samples**: Extend `openalex_offline.py` with additional concepts/authors to demonstrate richer scenarios without network access.

---

## Troubleshooting

- **No charts / empty data**: Check backend logs. If OpenAlex is unreachable, the backend should log warnings and still serve offline data. Ensure the Flask process has not crashed.
- **CORS issues**: CORS is enabled (`flask_cors.CORS(app)`). When deploying, tighten the origin list as needed.
- **Rate limiting**: Grouping requests can be heavy. The backend already reduces `per_page` and retries without `select` on failure. Consider caching or increasing the mailto usage when moving to production.
- **React build errors**: Ensure Node 18+ is installed. Delete `node_modules` and rerun `npm install` if dependencies drift.

---

CollabNet is designed as a demonstrative sandbox: every response is structured to keep the UI responsive whether or not the network is available. Dive into the code, adjust the analytics, and tailor the research matching engine to your needs!
