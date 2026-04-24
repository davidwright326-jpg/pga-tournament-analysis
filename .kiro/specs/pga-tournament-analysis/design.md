# Design: PGA Tournament Analysis Tool

## Architecture Overview

The application follows a three-tier architecture:

1. **Data Layer** — Python backend that scrapes/fetches PGA Tour data via the public GraphQL API (`orchestrator.pgatour.com/graphql`) and stores it locally in SQLite
2. **Analysis Engine** — Python module that performs statistical correlation analysis on historical course data and computes player fit scores
3. **Web Dashboard** — React (Next.js) frontend that displays tournament context, stat importance, and player rankings

```
┌─────────────────────────────────────────────────────┐
│                  Next.js Frontend                    │
│  (Dashboard, Charts, Player Rankings, Filters)       │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────┐
│               FastAPI Backend                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ Data Fetcher │  │ Analysis     │  │ Scheduler │  │
│  │ (PGA GraphQL)│  │ Engine       │  │ (APScheduler)│
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘  │
│         │                 │                │         │
│  ┌──────▼─────────────────▼────────────────▼──────┐  │
│  │              SQLite Database                    │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend API | Python 3.11+ / FastAPI | Fast async API, great for data processing |
| Data Fetching | httpx | Async HTTP client for GraphQL requests |
| Database | SQLite (via SQLAlchemy) | Zero-config, file-based, sufficient for single-user analytics |
| Analysis | pandas + scipy | Statistical correlation, data manipulation |
| Scheduler | APScheduler | Lightweight cron-like scheduling for weekly refreshes |
| Frontend | Next.js 14 (App Router) | React-based, SSR support, good DX |
| Charts | Recharts | Lightweight React charting library |
| Styling | Tailwind CSS | Utility-first, responsive design |
| Testing | pytest + Hypothesis (backend), Vitest + fast-check (frontend) |

## Data Model

### Database Schema (SQLite)

```sql
-- Tournament schedule and course info
CREATE TABLE tournaments (
    id TEXT PRIMARY KEY,           -- PGA Tour tournament ID (e.g., "R2026015")
    name TEXT NOT NULL,
    course_name TEXT NOT NULL,
    city TEXT,
    state TEXT,
    country TEXT,
    par INTEGER,
    yardage INTEGER,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    season INTEGER NOT NULL,
    purse REAL
);

-- Historical tournament results (past winners/top finishers)
CREATE TABLE tournament_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    season INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT,                  -- "1", "T2", "CUT", etc.
    total_score INTEGER,
    par_relative_score INTEGER,
    rounds_played INTEGER,
    UNIQUE(tournament_id, season, player_id)
);

-- Player stats per season
CREATE TABLE player_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    season INTEGER NOT NULL,
    stat_category TEXT NOT NULL,    -- e.g., "sg_off_tee", "sg_approach", "driving_distance"
    stat_value REAL,
    stat_rank INTEGER,
    UNIQUE(player_id, season, stat_category)
);

-- Course stat importance (analysis output)
CREATE TABLE course_stat_weights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    stat_category TEXT NOT NULL,
    weight REAL NOT NULL,           -- 0.0 to 1.0, normalized importance
    explanation TEXT,               -- Why this stat matters for this course
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, stat_category)
);

-- Computed player fit scores
CREATE TABLE player_fit_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id TEXT NOT NULL REFERENCES tournaments(id),
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    composite_score REAL NOT NULL,
    world_ranking INTEGER,
    fedex_ranking INTEGER,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, player_id)
);
```

### Stat Categories

The system tracks these stat categories (mapped to PGA Tour stat IDs):

| Category Key | Display Name | PGA Stat ID |
|-------------|-------------|-------------|
| sg_total | SG: Total | 02675 |
| sg_off_tee | SG: Off-the-Tee | 02567 |
| sg_approach | SG: Approach the Green | 02568 |
| sg_around_green | SG: Around-the-Green | 02569 |
| sg_putting | SG: Putting | 02564 |
| sg_tee_to_green | SG: Tee-to-Green | 02674 |
| driving_distance | Driving Distance | 101 |
| driving_accuracy | Driving Accuracy % | 102 |
| gir | Greens in Regulation % | 103 |
| scrambling | Scrambling % | 130 |
| birdie_avg | Birdie Average | 156 |
| scoring_avg | Scoring Average | 120 |

## Key Algorithms

### 1. Course Stat Importance Analysis

The analysis engine determines which stats matter most at a given course by:

1. **Fetch historical data**: Get top-10 finishers at the course for the last 5-10 years
2. **Compute correlation**: For each stat category, calculate the Spearman rank correlation between a player's stat value and their finishing position at that course
3. **Normalize weights**: Convert correlation coefficients to normalized importance weights (0-1 scale, summing to 1)
4. **Generate explanations**: Map stat importance to course characteristics (e.g., high driving accuracy weight → narrow fairways)

```python
def compute_stat_weights(tournament_id: str, seasons: list[int]) -> dict[str, float]:
    """
    Returns a dict mapping stat_category -> normalized_weight.
    
    Steps:
    1. Query tournament_results for top-10 finishers across given seasons
    2. For each finisher, look up their player_stats for that season
    3. For each stat category, compute Spearman correlation between
       stat_value and finish_position (lower position = better)
    4. Take absolute value of negative correlations (better stat → better finish)
    5. Normalize so all weights sum to 1.0
    """
    # Implementation in analysis/engine.py
```

### 2. Composite Fit Score Calculation

```python
def compute_fit_score(
    player_stats: dict[str, float],
    stat_weights: dict[str, float],
    stat_percentiles: dict[str, tuple[float, float]]  # (mean, std) for z-score
) -> float:
    """
    Composite score = sum(weight_i * z_score_i) for each stat category.
    
    z_score_i = (player_stat_i - mean_i) / std_i
    
    This normalizes stats to a common scale before weighting.
    Higher composite score = better fit for the course.
    """
```

### 3. Recency Weighting

Player stats are weighted by recency using exponential decay:

```python
def apply_recency_weight(stat_value: float, weeks_ago: int, half_life: int = 12) -> float:
    """Weight = 2^(-weeks_ago / half_life)"""
    return stat_value * (2 ** (-weeks_ago / half_life))
```

### 4. Course Archetype Fallback

When a course has fewer than 3 years of historical data:

1. Classify the course by archetype based on available metadata (par, yardage, location/climate)
2. Use aggregate stats from similar courses in the same archetype
3. Archetypes: "links", "parkland_long", "parkland_short", "desert", "coastal", "mountain"

## API Endpoints (FastAPI)

```
GET  /api/tournament/current          → Current week's tournament details
GET  /api/tournament/{id}/stats       → Stat importance weights for a tournament
GET  /api/tournament/{id}/history     → Past winners and their stats
GET  /api/players/rankings?tournament_id={id}&limit=50&min_rank=&filter_stat=
                                      → Ranked player list with fit scores
GET  /api/players/{id}/profile?tournament_id={id}
                                      → Player detail with stat comparison
POST /api/refresh                     → Trigger manual data refresh
GET  /api/status                      → System status, last refresh time
```

## Frontend Pages

### Dashboard (/)
- Tournament header card (name, course, dates, par, yardage)
- Stat importance chart (radar or horizontal bar chart)
- Player rankings table (sortable, filterable)
- Last updated indicator

### Player Detail (/player/[id])
- Player info card
- Stat comparison chart (player vs. course ideal vs. historical winner avg)
- Course history table (past results at this course)

### Course History (/history)
- Past winners table (last 5-10 years)
- Historical stat averages for winners
- Compare tool (select a player to overlay)

## Data Refresh Pipeline

```
Weekly Cron (Tuesday 6:00 AM ET)
  │
  ├─ 1. Fetch current tournament schedule
  │     POST orchestrator.pgatour.com/graphql → TournamentSchedule query
  │
  ├─ 2. Identify current week's tournament
  │     Match by date range
  │
  ├─ 3. Fetch/update player stats (current season)
  │     POST orchestrator.pgatour.com/graphql → StatDetails query (per stat ID)
  │
  ├─ 4. Fetch historical results for current course
  │     POST orchestrator.pgatour.com/graphql → TournamentPastResults query
  │
  ├─ 5. Run course stat importance analysis
  │     compute_stat_weights()
  │
  ├─ 6. Compute player fit scores
  │     compute_fit_score() for each player in field
  │
  └─ 7. Update database & log status
```

## PGA Tour GraphQL API Details

The PGA Tour website uses a GraphQL API at `https://orchestrator.pgatour.com/graphql` with an API key header.

Key queries:
- **TournamentPastResults**: Historical results by tournament ID and year
- **StatDetails**: Player stats by stat ID and season
- **Schedule**: Tournament schedule for a season

Headers required:
```
x-api-key: da2-gsrx5bibzbb4njvhl7t37wqyl4
Content-Type: application/json
```

> Note: This is a public API key used by the PGA Tour website frontend. It may change; the system should handle API key rotation gracefully.

## Correctness Properties

These properties define the formal correctness criteria that the implementation must satisfy. They will be validated using property-based testing.

### P1: Stat Weight Normalization (Validates: Requirements 2.2)
For any course analysis output, all stat weights must be non-negative and sum to 1.0 (within floating-point tolerance of 0.001). No individual weight may exceed 1.0.

```
∀ weights ∈ compute_stat_weights(tournament, seasons):
  ∀ w ∈ weights.values(): 0.0 ≤ w ≤ 1.0
  |sum(weights.values()) - 1.0| < 0.001
```

### P2: Stat Category Completeness (Validates: Requirements 2.3)
The analysis output must always include weights for all required stat categories (the 12 categories defined in the stat categories table). No category may be missing from the output.

```
∀ output ∈ compute_stat_weights(tournament, seasons):
  REQUIRED_CATEGORIES ⊆ output.keys()
```

### P3: Player Ranking Order Consistency (Validates: Requirements 3.1, 3.3)
The player ranking list must be sorted in strictly descending order by composite fit score. For any two adjacent players in the list, the higher-ranked player must have a composite score ≥ the lower-ranked player.

```
∀ rankings ∈ generate_rankings(tournament):
  ∀ i ∈ [0, len(rankings)-2]:
    rankings[i].composite_score ≥ rankings[i+1].composite_score
```

### P4: Composite Score Correctness (Validates: Requirements 3.3)
The composite fit score for any player must equal the weighted sum of their z-scored stats using the course stat weights. Given the same inputs, the score must be deterministic.

```
∀ player, weights, percentiles:
  expected = sum(weights[cat] * z_score(player.stats[cat], percentiles[cat]) for cat in weights)
  |compute_fit_score(player.stats, weights, percentiles) - expected| < 0.0001
```

### P5: Filter Subset Property (Validates: Requirements 3.5)
Applying any filter to the player rankings must produce a result that is a strict subset of (or equal to) the unfiltered rankings. No player should appear in filtered results that wasn't in the unfiltered results.

```
∀ filter_params:
  set(filter(rankings, filter_params)) ⊆ set(rankings)
```

### P6: Recency Weight Monotonicity (Validates: Requirements 3.4)
The recency weight function must be monotonically decreasing with respect to time. A stat from week N must always receive a higher weight than the same stat from week N+K (K > 0).

```
∀ stat_value, weeks_ago, k > 0:
  apply_recency_weight(stat_value, weeks_ago) > apply_recency_weight(stat_value, weeks_ago + k)
```

### P7: Historical Comparison Delta Correctness (Validates: Requirements 6.2, 6.3)
The delta between a player's stat and the historical winner average must equal exactly player_stat - winner_avg. Highlighting must be applied if and only if |delta| exceeds the defined threshold.

```
∀ player_stat, winner_avg, threshold:
  delta = player_stat - winner_avg
  compute_delta(player_stat, winner_avg) == delta
  is_highlighted(delta, threshold) ⟺ |delta| > threshold
```

### P8: Sort Stability (Validates: Requirements 4.3)
Sorting the player rankings table by any column must produce a valid total order for that column. Re-sorting by the same column must produce the same result (idempotent).

```
∀ column ∈ sortable_columns:
  sorted_once = sort(rankings, column)
  sorted_twice = sort(sort(rankings, column), column)
  sorted_once == sorted_twice
  is_ordered(sorted_once, column)
```

### P9: Current Tournament Resolution (Validates: Requirements 1.2)
Given a date, the tournament resolver must return the tournament whose date range contains that date, or the next upcoming tournament if no tournament is active. The result must be deterministic for any given date.

```
∀ date:
  result = resolve_current_tournament(date, schedule)
  result.start_date ≤ date ≤ result.end_date  ∨
  (result.start_date > date ∧ ¬∃ t ∈ schedule: t.start_date ≤ date ≤ t.end_date)
```

## Testing Strategy

| Property | Test Type | Framework | Location |
|----------|-----------|-----------|----------|
| P1 | Property-based | Hypothesis | backend/tests/test_analysis.py |
| P2 | Property-based | Hypothesis | backend/tests/test_analysis.py |
| P3 | Property-based | Hypothesis | backend/tests/test_rankings.py |
| P4 | Property-based | Hypothesis | backend/tests/test_rankings.py |
| P5 | Property-based | Hypothesis | backend/tests/test_rankings.py |
| P6 | Property-based | Hypothesis | backend/tests/test_recency.py |
| P7 | Property-based | Hypothesis | backend/tests/test_comparison.py |
| P8 | Property-based | fast-check | frontend/tests/sort.test.ts |
| P9 | Property-based | Hypothesis | backend/tests/test_tournament.py |
