"""
PGA Tournament Analysis — Streamlit Dashboard

Reads directly from the SQLite database and reuses the backend analysis modules.
Run with: streamlit run streamlit_app.py
"""
import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import threading
import asyncio

from app.database import SessionLocal, init_db
from app.models import (
    Tournament, TournamentResult, PlayerStat, CourseStatWeight,
    PlayerFitScore, EventPlayerStat, TournamentField,
)
from app.data.tournament_resolver import resolve_current_tournament
from app.analysis.engine import generate_explanation
from app.analysis.scoring import compute_comparison_delta, is_highlighted
from app.config import STAT_CATEGORIES, HIGHLIGHT_THRESHOLD

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PGA Tournament Analysis",
    page_icon="⛳",
    layout="wide",
)

STAT_LABELS = {
    # Strokes Gained
    "sg_total": "SG: Total",
    "sg_off_tee": "SG: Off-the-Tee",
    "sg_approach": "SG: Approach",
    "sg_around_green": "SG: Around Green",
    "sg_putting": "SG: Putting",
    "sg_tee_to_green": "SG: Tee-to-Green",
    # Off the Tee
    "driving_distance": "Driving Distance",
    "driving_accuracy": "Driving Accuracy %",
    "total_driving": "Total Driving",
    "club_head_speed": "Club Head Speed",
    "ball_speed": "Ball Speed",
    "good_drive_pct": "Good Drive %",
    # Approach
    "gir": "GIR %",
    "proximity_to_hole": "Proximity to Hole",
    "approach_over_100": "Approach from > 100 yds",
    "approach_inside_100": "Approach from < 100 yds",
    "gir_from_200_plus": "GIR % from 200+ yds",
    # Around the Green
    "scrambling": "Scrambling %",
    "sand_save_pct": "Sand Save %",
    "proximity_arg": "Proximity to Hole (ARG)",
    # Putting
    "putting_avg": "Putting Average",
    "putts_per_round": "Putts Per Round",
    "one_putt_pct": "One-Putt %",
    "three_putt_avoid": "3-Putt Avoidance",
    "putting_inside_10": "Putting Inside 10'",
    "putting_10_15": "Putting from 10-15'",
    "putting_15_20": "Putting from 15-20'",
    "putting_over_20": "Putting from > 20'",
    "birdie_conversion": "Birdie/Better Conv %",
    # Scoring
    "birdie_avg": "Birdie Average",
    "scoring_avg": "Scoring Average",
    "par3_scoring": "Par 3 Scoring Avg",
    "par4_scoring": "Par 4 Scoring Avg",
    "par5_scoring": "Par 5 Scoring Avg",
    "bogey_avoid": "Bogey Avoidance",
    "bounce_back": "Bounce Back %",
    "eagles_per_hole": "Eagles per Hole",
    # Money / Rankings
    "fedex_pts": "FedExCup Points",
    "top10_finishes": "Top 10 Finishes",
}

DISPLAY_STATS = [
    "sg_total", "sg_off_tee", "sg_approach", "sg_putting",
    "driving_distance", "driving_accuracy", "gir", "scrambling",
]

SHORT_LABELS = {
    "sg_total": "SG:Tot", "sg_off_tee": "SG:OTT", "sg_approach": "SG:App",
    "sg_around_green": "SG:AtG", "sg_putting": "SG:Put", "sg_tee_to_green": "SG:T2G",
    "driving_distance": "DD", "driving_accuracy": "DA%", "total_driving": "TotDrv",
    "club_head_speed": "CHS", "ball_speed": "BallSpd", "good_drive_pct": "GdDrv%",
    "gir": "GIR%", "proximity_to_hole": "Prox", "approach_over_100": "App>100",
    "approach_inside_100": "App<100", "gir_from_200_plus": "GIR200+",
    "scrambling": "Scr%", "sand_save_pct": "SS%", "proximity_arg": "ProxARG",
    "putting_avg": "PutAvg", "putts_per_round": "PPR", "one_putt_pct": "1Put%",
    "three_putt_avoid": "3PutAv", "putting_inside_10": "Put<10",
    "putting_10_15": "Put10-15", "putting_15_20": "Put15-20", "putting_over_20": "Put>20",
    "birdie_conversion": "BirdConv",
    "birdie_avg": "Bird", "scoring_avg": "Scoring",
    "par3_scoring": "Par3", "par4_scoring": "Par4", "par5_scoring": "Par5",
    "bogey_avoid": "BogAv", "bounce_back": "BB%", "eagles_per_hole": "Eagle",
    "fedex_pts": "FedEx", "top10_finishes": "Top10",
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
@st.cache_resource
def get_db():
    init_db()
    return SessionLocal


def db_session():
    Session = get_db()
    return Session()


def _needs_initial_data() -> bool:
    """Check if the database has any tournament data yet."""
    db = db_session()
    try:
        count = db.query(Tournament).count()
        return count == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_current_tournament():
    db = db_session()
    try:
        tournaments = db.query(Tournament).order_by(Tournament.start_date).all()
        current = resolve_current_tournament(date.today(), tournaments)
        return current
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_stat_weights(tournament_id: str):
    db = db_session()
    try:
        weights = (
            db.query(CourseStatWeight)
            .filter(CourseStatWeight.tournament_id == tournament_id)
            .all()
        )
        if not weights:
            return []
        weight_dict = {w.stat_category: w.weight for w in weights}
        result = []
        for w in weights:
            cat_info = STAT_CATEGORIES.get(w.stat_category, {})
            result.append({
                "category": w.stat_category,
                "display_name": cat_info.get("name", w.stat_category),
                "weight": w.weight,
                "explanation": w.explanation or generate_explanation(
                    w.stat_category, w.weight, weight_dict
                ),
            })
        result.sort(key=lambda x: x["weight"], reverse=True)
        return result
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_tournament_field(tournament_id: str) -> set:
    """Load the set of player IDs in the official tournament field."""
    db = db_session()
    try:
        players = (
            db.query(TournamentField.player_id)
            .filter(TournamentField.tournament_id == tournament_id)
            .all()
        )
        return {p[0] for p in players}
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_player_rankings(tournament_id: str, limit: int = 200):
    db = db_session()
    try:
        scores = (
            db.query(PlayerFitScore)
            .filter(PlayerFitScore.tournament_id == tournament_id)
            .order_by(PlayerFitScore.composite_score.desc())
            .limit(limit)
            .all()
        )
        result = []
        for rank, s in enumerate(scores, 1):
            player_stats = (
                db.query(PlayerStat)
                .filter(PlayerStat.player_id == s.player_id)
                .order_by(PlayerStat.season.desc())
                .all()
            )
            stat_dict = {}
            stat_ranks = {}
            for ps in player_stats:
                if ps.stat_category not in stat_dict and ps.stat_value is not None:
                    stat_dict[ps.stat_category] = ps.stat_value
                    stat_ranks[ps.stat_category] = ps.stat_rank
            result.append({
                "rank": rank,
                "player_id": s.player_id,
                "player_name": s.player_name,
                "composite_score": s.composite_score,
                "world_ranking": s.world_ranking,
                "fedex_ranking": s.fedex_ranking,
                "stats": stat_dict,
                "stat_ranks": stat_ranks,
            })
        return result
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_tournament_history(tournament_id: str, limit: int = 10):
    db = db_session()
    try:
        current_year = date.today().year
        winners = (
            db.query(TournamentResult)
            .filter(
                TournamentResult.tournament_id == tournament_id,
                TournamentResult.position == "1",
                TournamentResult.season < current_year,
            )
            .order_by(TournamentResult.season.desc())
            .all()
        )
        seen_seasons = set()
        unique_winners = []
        for w in winners:
            if w.season not in seen_seasons:
                seen_seasons.add(w.season)
                unique_winners.append(w)
        unique_winners = unique_winners[:limit]

        result = []
        for w in unique_winners:
            event_stats = (
                db.query(EventPlayerStat)
                .filter(
                    EventPlayerStat.player_id == w.player_id,
                    EventPlayerStat.season == w.season,
                )
                .all()
            )
            stat_dict = {s.stat_category: s.stat_value for s in event_stats if s.stat_value is not None}
            stat_ranks = {s.stat_category: s.stat_rank for s in event_stats if s.stat_rank is not None}
            if not stat_dict:
                stats = (
                    db.query(PlayerStat)
                    .filter(PlayerStat.player_id == w.player_id)
                    .order_by(PlayerStat.season.desc())
                    .all()
                )
                for s in stats:
                    if s.stat_category not in stat_dict and s.stat_value is not None:
                        stat_dict[s.stat_category] = s.stat_value
                    if s.stat_category not in stat_ranks and s.stat_rank is not None:
                        stat_ranks[s.stat_category] = s.stat_rank
            result.append({
                "season": w.season,
                "player_id": w.player_id,
                "player_name": w.player_name,
                "position": w.position,
                "total_score": w.total_score,
                "par_relative_score": w.par_relative_score,
                "stats": stat_dict,
                "stat_ranks": stat_ranks,
            })
        return result
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_player_profile(player_id: str, tournament_id: str):
    db = db_session()
    try:
        fit_score = (
            db.query(PlayerFitScore)
            .filter(
                PlayerFitScore.tournament_id == tournament_id,
                PlayerFitScore.player_id == player_id,
            )
            .first()
        )
        if not fit_score:
            return None

        player_stats = (
            db.query(PlayerStat)
            .filter(PlayerStat.player_id == player_id)
            .order_by(PlayerStat.season.desc())
            .all()
        )
        stat_dict = {}
        for ps in player_stats:
            if ps.stat_category not in stat_dict and ps.stat_value is not None:
                stat_dict[ps.stat_category] = ps.stat_value

        weights = (
            db.query(CourseStatWeight)
            .filter(CourseStatWeight.tournament_id == tournament_id)
            .all()
        )
        weight_dict = {w.stat_category: w.weight for w in weights}

        winners = (
            db.query(TournamentResult)
            .filter(
                TournamentResult.tournament_id == tournament_id,
                TournamentResult.position == "1",
            )
            .all()
        )
        winner_stats_agg = {}
        for w in winners:
            w_stats = (
                db.query(PlayerStat)
                .filter(PlayerStat.player_id == w.player_id, PlayerStat.season == w.season)
                .all()
            )
            for ws in w_stats:
                if ws.stat_value is not None:
                    winner_stats_agg.setdefault(ws.stat_category, []).append(ws.stat_value)
        winner_avgs = {k: sum(v) / len(v) for k, v in winner_stats_agg.items() if v}

        comparison = []
        for cat_key, cat_info in STAT_CATEGORIES.items():
            player_val = stat_dict.get(cat_key)
            winner_avg = winner_avgs.get(cat_key)
            weight = weight_dict.get(cat_key, 0)
            delta = None
            highlighted = False
            if player_val is not None and winner_avg is not None:
                delta = compute_comparison_delta(player_val, winner_avg)
                highlighted = is_highlighted(delta, HIGHLIGHT_THRESHOLD)
            comparison.append({
                "category": cat_key,
                "display_name": cat_info["name"],
                "player_value": player_val,
                "winner_avg": round(winner_avg, 3) if winner_avg else None,
                "delta": round(delta, 3) if delta is not None else None,
                "highlighted": highlighted,
                "weight": weight,
            })
        comparison.sort(key=lambda x: x["weight"], reverse=True)

        return {
            "player_id": player_id,
            "player_name": fit_score.player_name,
            "composite_score": fit_score.composite_score,
            "world_ranking": fit_score.world_ranking,
            "fedex_ranking": fit_score.fedex_ranking,
            "comparison": comparison,
        }
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_season_results(season: int):
    db = db_session()
    try:
        today = date.today()
        tournaments = (
            db.query(Tournament)
            .filter(Tournament.season == season, Tournament.start_date <= today)
            .order_by(Tournament.start_date.desc())
            .all()
        )
        results = []
        for t in tournaments:
            winner = (
                db.query(TournamentResult)
                .filter(
                    TournamentResult.tournament_id == t.id,
                    TournamentResult.position == "1",
                    TournamentResult.season == season,
                )
                .first()
            )
            if not winner:
                winner = (
                    db.query(TournamentResult)
                    .filter(
                        TournamentResult.tournament_id == t.id,
                        TournamentResult.position == "1",
                    )
                    .first()
                )
            results.append({
                "tournament": t,
                "winner": winner,
            })
        return results
    finally:
        db.close()


def load_refresh_status():
    """Load refresh status from the system module (in-memory)."""
    try:
        from app.routes.system import _refresh_status
        return dict(_refresh_status)
    except Exception:
        return {"status": "unknown", "last_refresh": None, "error": None}


@st.cache_data(ttl=300)
def load_all_player_stats(season: int):
    """Load all player stats for a season, grouped by player."""
    db = db_session()
    try:
        all_stats = (
            db.query(PlayerStat)
            .filter(PlayerStat.season == season, PlayerStat.stat_value.isnot(None))
            .all()
        )
        players = {}
        for s in all_stats:
            if s.player_id not in players:
                players[s.player_id] = {"player_name": s.player_name, "stats": {}, "ranks": {}}
            players[s.player_id]["stats"][s.stat_category] = s.stat_value
            if s.stat_rank is not None:
                players[s.player_id]["ranks"][s.stat_category] = s.stat_rank
        return players
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_player_season_results(player_id: str, season: int):
    """Load a player's results across all tournaments in a season."""
    db = db_session()
    try:
        results = (
            db.query(TournamentResult)
            .filter(
                TournamentResult.player_id == player_id,
                TournamentResult.season == season,
            )
            .all()
        )
        out = []
        for r in results:
            t = db.query(Tournament).filter(Tournament.id == r.tournament_id).first()
            out.append({
                "tournament_name": t.name if t else r.tournament_id,
                "course_name": t.course_name if t else "—",
                "start_date": t.start_date if t else None,
                "position": r.position,
                "total_score": r.total_score,
                "par_relative_score": r.par_relative_score,
                "rounds_played": r.rounds_played,
            })
        out.sort(key=lambda x: x["start_date"] or date.min, reverse=True)
        return out
    finally:
        db.close()


@st.cache_data(ttl=300)
def load_player_course_history(player_id: str, tournament_id: str):
    """Load a player's past results at a specific tournament/course."""
    db = db_session()
    try:
        results = (
            db.query(TournamentResult)
            .filter(
                TournamentResult.player_id == player_id,
                TournamentResult.tournament_id == tournament_id,
            )
            .order_by(TournamentResult.season.desc())
            .all()
        )
        return [
            {
                "season": r.season,
                "position": r.position,
                "total_score": r.total_score,
                "par_relative_score": r.par_relative_score,
                "rounds_played": r.rounds_played,
            }
            for r in results
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Refresh trigger
# ---------------------------------------------------------------------------
def trigger_refresh():
    """Run the full data refresh pipeline in a background thread."""
    from app.routes.system import _run_refresh_sync
    thread = threading.Thread(target=_run_refresh_sync, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("⛳ PGA Analysis")
page = st.sidebar.radio(
    "Navigate",
    ["🏠 Dashboard", "🎯 Custom Rankings", "📊 Player Detail", "📜 Course History", "🏆 Season Results"],
    label_visibility="collapsed",
)

# Refresh controls in sidebar
st.sidebar.markdown("---")
status = load_refresh_status()
if status.get("last_refresh"):
    st.sidebar.caption(f"Last updated: {status['last_refresh']}")
else:
    st.sidebar.caption("No data refresh recorded yet")

if st.sidebar.button("🔄 Refresh Data", disabled=status.get("status") == "running"):
    trigger_refresh()
    st.sidebar.success("Refresh started! Reload in a minute to see new data.")
    st.cache_data.clear()

if status.get("status") == "running":
    st.sidebar.info("Refresh in progress…")
if status.get("error"):
    st.sidebar.error(f"Last error: {status['error']}")

# Auto-bootstrap: if DB is empty (fresh cloud deploy), trigger a refresh
if _needs_initial_data() and status.get("status") != "running":
    st.info("⏳ First run detected — fetching PGA data. This takes about a minute. Please reload shortly.")
    trigger_refresh()


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------
if page == "🏠 Dashboard":
    tournament = load_current_tournament()

    if not tournament:
        st.warning("No tournament scheduled for this week. Check back later!")
        st.stop()

    # Tournament header
    location = ", ".join(filter(None, [tournament.city, tournament.state]))
    st.title(f"⛳ {tournament.name}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Course", tournament.course_name)
    col2.metric("Location", location or "—")
    col3.metric("Par", tournament.par or "—")
    col4.metric("Yardage", f"{tournament.yardage:,}" if tournament.yardage else "—")

    dates_str = ""
    if tournament.start_date and tournament.end_date:
        dates_str = f"{tournament.start_date.strftime('%b %d')} – {tournament.end_date.strftime('%b %d, %Y')}"
    if tournament.purse:
        dates_str += f"  •  Purse: ${tournament.purse / 1_000_000:.1f}M"
    st.caption(dates_str)

    st.markdown("---")

    # Stat importance — vertical columns with top 5 players
    stat_weights = load_stat_weights(tournament.id)
    if stat_weights:
        st.subheader("Key Stats for This Course")

        # Load all player stats for ranking within each category
        current_year = date.today().year
        all_players = load_all_player_stats(current_year)

        # Determine how many stat columns to show (top weighted)
        top_weights = stat_weights[:6]
        cols = st.columns(len(top_weights))

        for i, sw in enumerate(top_weights):
            cat = sw["category"]
            weight_pct = sw["weight"] * 100
            display = sw["display_name"]

            # Rank players by this stat (higher is better for most stats)
            players_with_stat = []
            for pid, pdata in all_players.items():
                val = pdata["stats"].get(cat)
                if val is not None:
                    players_with_stat.append({
                        "name": pdata["player_name"],
                        "value": val,
                        "rank": pdata["ranks"].get(cat),
                    })

            # Sort: for scoring avg, putts per round, par scoring — lower is better
            lower_is_better = cat in (
                "scoring_avg", "putting_avg", "putts_per_round",
                "par3_scoring", "par4_scoring", "par5_scoring",
                "three_putt_avoid", "proximity_to_hole", "proximity_arg",
                "approach_over_100", "approach_inside_100",
            )
            players_with_stat.sort(
                key=lambda x: x["value"],
                reverse=not lower_is_better,
            )
            top5 = players_with_stat[:5]

            with cols[i]:
                st.markdown(f'<p style="color:#15803d; font-size:1.1rem; font-weight:700; margin-bottom:0;">{display}</p>', unsafe_allow_html=True)
                st.caption(f"Weight: {weight_pct:.1f}%")
                for j, p in enumerate(top5, 1):
                    rank_str = f" (#{p['rank']})" if p["rank"] else ""
                    st.markdown(f"{j}. **{p['name']}**  \n{p['value']:.2f}{rank_str}")
                if not top5:
                    st.caption("No data")

        with st.expander("Stat explanations"):
            for s in stat_weights:
                st.markdown(f"**{s['display_name']}** ({s['weight']*100:.1f}%): {s['explanation']}")

    st.markdown("---")

    # Player rankings table
    rankings = load_player_rankings(tournament.id)
    field_ids = load_tournament_field(tournament.id)

    # Filter to field only if we have field data
    if field_ids:
        rankings = [r for r in rankings if r["player_id"] in field_ids]
        field_note = f"Showing {len(rankings)} players in the official field"
    else:
        field_note = "⚠️ No field data available — showing all ranked players. Refresh data to fetch the field."

    if rankings:
        st.subheader("Player Rankings")
        st.caption(field_note)

        # Filters
        fcol1, fcol2, fcol3 = st.columns([1, 1, 1])
        with fcol1:
            max_rank = st.number_input("Max World Rank", min_value=1, value=500, step=10,
                                       help="Filter disabled — no world rankings in data yet" if not any(r["world_ranking"] for r in rankings) else "")
        with fcol2:
            stat_filter_key = st.selectbox("Stat threshold", ["None"] + list(STAT_LABELS.keys()),
                                           format_func=lambda x: SHORT_LABELS.get(x, x))
        with fcol3:
            stat_filter_val = st.number_input("Min value", value=0.0, step=0.1,
                                              disabled=stat_filter_key == "None")

        filtered = rankings
        if max_rank < 200:
            # Only apply filter if at least some players have world rankings
            ranked_players = [r for r in filtered if r["world_ranking"] is not None]
            if ranked_players:
                filtered = [r for r in filtered
                            if r["world_ranking"] is not None and r["world_ranking"] <= max_rank]
        if stat_filter_key != "None" and stat_filter_val:
            filtered = [r for r in filtered
                        if r["stats"].get(stat_filter_key) is not None
                        and r["stats"][stat_filter_key] >= stat_filter_val]

        # Determine top stats to show
        top_stats = [s["category"] for s in stat_weights[:6]] if stat_weights else DISPLAY_STATS[:6]

        # Build dataframe
        rows = []
        for i, r in enumerate(filtered, 1):
            row = {
                "#": i,
                "Player": r["player_name"],
                "OWGR": r["world_ranking"] or "—",
                "Fit Score": round(r["composite_score"], 3),
            }
            for cat in top_stats:
                val = r["stats"].get(cat)
                row[SHORT_LABELS.get(cat, cat)] = round(val, 2) if val is not None else None
            row["_player_id"] = r["player_id"]
            rows.append(row)

        df_rankings = pd.DataFrame(rows)
        display_cols = [c for c in df_rankings.columns if not c.startswith("_")]

        st.dataframe(
            df_rankings[display_cols],
            use_container_width=True,
            hide_index=True,
            height=min(600, 40 + len(filtered) * 35),
        )
        st.caption(f"Showing {len(filtered)} of {len(rankings)} players")
    else:
        st.info("No player rankings available. Try refreshing data.")


# ---------------------------------------------------------------------------
# Player Detail page
# ---------------------------------------------------------------------------
elif page == "📊 Player Detail":
    tournament = load_current_tournament()
    if not tournament:
        st.warning("No tournament scheduled for this week.")
        st.stop()

    rankings = load_player_rankings(tournament.id)
    if not rankings:
        st.info("No player data available. Try refreshing data.")
        st.stop()

    player_options = {r["player_name"]: r["player_id"] for r in rankings}
    selected_name = st.selectbox("Select a player", list(player_options.keys()))
    selected_id = player_options[selected_name]

    profile = load_player_profile(selected_id, tournament.id)
    if not profile:
        st.error("Player profile not found.")
        st.stop()

    # Player info
    st.title(f"📊 {profile['player_name']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Fit Score", f"{profile['composite_score']:.3f}")
    col2.metric("World Ranking", f"#{profile['world_ranking']}" if profile["world_ranking"] else "—")
    col3.metric("FedEx Ranking", f"#{profile['fedex_ranking']}" if profile["fedex_ranking"] else "—")

    st.markdown("---")

    # Comparison chart (top weighted stats only for readability)
    comp = profile["comparison"]
    chart_data = [c for c in comp if c["player_value"] is not None and c["winner_avg"] is not None]

    if chart_data:
        st.subheader("Stat Comparison: Player vs. Historical Winners")
        # Show top 12 by weight in the chart, full list in the table below
        chart_top = chart_data[:12]
        df_comp = pd.DataFrame(chart_top)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df_comp["display_name"],
            x=df_comp["player_value"],
            name="Player",
            orientation="h",
            marker_color=["#16a34a" if d and d > 0 else "#dc2626" if d and d < 0 else "#15803d"
                          for d, h in zip(df_comp["delta"], df_comp["highlighted"])],
        ))
        fig.add_trace(go.Bar(
            y=df_comp["display_name"],
            x=df_comp["winner_avg"],
            name="Winner Avg",
            orientation="h",
            marker_color="#9ca3af",
        ))
        fig.update_layout(
            barmode="group",
            height=max(350, len(chart_top) * 45),
            margin=dict(l=0, r=20, t=10, b=10),
            yaxis=dict(autorange="reversed"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Full stats grouped by category
    st.subheader("All Stats by Category")

    STAT_GROUPS = {
        "Strokes Gained": ["sg_total", "sg_off_tee", "sg_approach", "sg_around_green", "sg_putting", "sg_tee_to_green"],
        "Off the Tee": ["driving_distance", "driving_accuracy", "total_driving", "club_head_speed", "ball_speed", "good_drive_pct"],
        "Approach the Green": ["gir", "proximity_to_hole", "approach_over_100", "approach_inside_100", "gir_from_200_plus"],
        "Around the Green": ["scrambling", "sand_save_pct", "proximity_arg"],
        "Putting": ["putting_avg", "putts_per_round", "one_putt_pct", "three_putt_avoid", "putting_inside_10", "putting_10_15", "putting_15_20", "putting_over_20", "birdie_conversion"],
        "Scoring": ["birdie_avg", "scoring_avg", "par3_scoring", "par4_scoring", "par5_scoring", "bogey_avoid", "bounce_back", "eagles_per_hole"],
        "Rankings": ["fedex_pts", "top10_finishes"],
    }

    comp_by_cat = {c["category"]: c for c in comp}

    for group_name, stat_keys in STAT_GROUPS.items():
        group_rows = []
        for cat in stat_keys:
            c = comp_by_cat.get(cat)
            if not c:
                continue
            delta_str = ""
            if c["delta"] is not None:
                delta_str = f"{'+' if c['delta'] > 0 else ''}{c['delta']:.3f}"
            tag = ""
            if c["highlighted"]:
                tag = "✅ Strength" if c["delta"] and c["delta"] > 0 else "⚠️ Weakness"
            group_rows.append({
                "Stat": c["display_name"],
                "Player": round(c["player_value"], 3) if c["player_value"] is not None else None,
                "Winner Avg": c["winner_avg"],
                "Delta": delta_str,
                "Weight": f"{c['weight']*100:.1f}%" if c["weight"] else "—",
                "": tag,
            })
        if group_rows:
            with st.expander(f"**{group_name}** ({len(group_rows)} stats)", expanded=(group_name == "Strokes Gained")):
                st.dataframe(pd.DataFrame(group_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # Season results for this player
    current_year = date.today().year
    season_results = load_player_season_results(selected_id, current_year)

    st.subheader(f"{current_year} Season Results")
    if season_results:
        sr_rows = []
        for r in season_results:
            score_str = "—"
            if r["par_relative_score"] is not None:
                score_str = f"{'+' if r['par_relative_score'] > 0 else ''}{r['par_relative_score']}"
            sr_rows.append({
                "Date": r["start_date"].strftime("%b %d") if r["start_date"] else "—",
                "Tournament": r["tournament_name"],
                "Course": r["course_name"],
                "Pos": r["position"] or "—",
                "Score": score_str,
                "Total": r["total_score"] or "—",
                "Rounds": r["rounds_played"] or "—",
            })
        st.dataframe(pd.DataFrame(sr_rows), use_container_width=True, hide_index=True)
        # Quick summary
        positions = [r["position"] for r in season_results if r["position"] and r["position"] not in ("CUT", "WD", "DQ", "MDF")]
        cuts = sum(1 for r in season_results if r["position"] == "CUT")
        wins = sum(1 for r in season_results if r["position"] == "1")
        top10s = 0
        for p in positions:
            try:
                pos_num = int(p.lstrip("T"))
                if pos_num <= 10:
                    top10s += 1
            except ValueError:
                pass
        st.caption(f"{len(season_results)} events  •  {wins} win(s)  •  {top10s} top-10s  •  {cuts} cut(s)")
    else:
        st.info("No results found for this player this season.")

    st.markdown("---")

    # Past results at this week's tournament
    course_results = load_player_course_history(selected_id, tournament.id)

    st.subheader(f"Past Results at {tournament.course_name}")
    if course_results:
        cr_rows = []
        for r in course_results:
            score_str = "—"
            if r["par_relative_score"] is not None:
                score_str = f"{'+' if r['par_relative_score'] > 0 else ''}{r['par_relative_score']}"
            cr_rows.append({
                "Year": r["season"],
                "Pos": r["position"] or "—",
                "Score": score_str,
                "Total": r["total_score"] or "—",
                "Rounds": r["rounds_played"] or "—",
            })
        st.dataframe(pd.DataFrame(cr_rows), use_container_width=True, hide_index=True)
        # Summary
        finishes = []
        for r in course_results:
            if r["position"] and r["position"] not in ("CUT", "WD", "DQ", "MDF"):
                try:
                    finishes.append(int(r["position"].lstrip("T")))
                except ValueError:
                    pass
        if finishes:
            st.caption(f"{len(course_results)} appearance(s)  •  Best finish: {min(finishes)}  •  Avg finish: {sum(finishes)/len(finishes):.0f}")
        else:
            st.caption(f"{len(course_results)} appearance(s)")
    else:
        st.info("No past results at this course for this player.")


# ---------------------------------------------------------------------------
# Course History page
# ---------------------------------------------------------------------------
elif page == "📜 Course History":
    tournament = load_current_tournament()
    if not tournament:
        st.warning("No tournament scheduled for this week.")
        st.stop()

    st.title(f"📜 Course History: {tournament.course_name}")
    st.caption("Past winners and their tournament-week stats")

    history = load_tournament_history(tournament.id)
    rankings = load_player_rankings(tournament.id)

    # Player comparison overlay
    if rankings:
        st.subheader("Player Comparison")
        st.caption("Select a player to compare their current stats against historical winner averages.")
        player_options = {"— None —": None}
        player_options.update({f"{r['player_name']} (Fit: {r['composite_score']:.3f})": r for r in rankings})
        selected_label = st.selectbox("Compare player", list(player_options.keys()))
        selected_player = player_options[selected_label]

        if selected_player and history:
            # Compute winner averages
            winner_avgs = {}
            for stat in DISPLAY_STATS:
                vals = [h["stats"].get(stat) for h in history if h["stats"].get(stat) is not None]
                winner_avgs[stat] = sum(vals) / len(vals) if vals else None

            comp_rows = []
            for stat in DISPLAY_STATS:
                player_val = selected_player["stats"].get(stat)
                avg = winner_avgs.get(stat)
                delta = (player_val - avg) if player_val is not None and avg is not None else None
                highlighted = delta is not None and abs(delta) > 0.5
                tag = ""
                if highlighted:
                    tag = "✅ Strength" if delta > 0 else "⚠️ Weakness"
                comp_rows.append({
                    "Stat": STAT_LABELS.get(stat, stat),
                    "Player": round(player_val, 2) if player_val is not None else None,
                    "Winner Avg": round(avg, 2) if avg is not None else None,
                    "Delta": f"{'+' if delta and delta > 0 else ''}{delta:.2f}" if delta is not None else "—",
                    "": tag,
                })
            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # Past winners table
    st.subheader("Past Winners")
    if history:
        hist_rows = []
        for h in history:
            score_str = ""
            if h["par_relative_score"] is not None:
                score_str = f"{'+' if h['par_relative_score'] > 0 else ''}{h['par_relative_score']}"
            row = {
                "Year": h["season"],
                "Winner": h["player_name"],
                "Score": score_str or "—",
                "Total": h["total_score"] or "—",
            }
            for stat in DISPLAY_STATS:
                val = h["stats"].get(stat)
                row[SHORT_LABELS.get(stat, stat)] = round(val, 2) if val is not None else None
            hist_rows.append(row)

        # Add winner average row
        avg_row = {"Year": "AVG", "Winner": "Winner Average", "Score": "—", "Total": "—"}
        for stat in DISPLAY_STATS:
            vals = [h["stats"].get(stat) for h in history if h["stats"].get(stat) is not None]
            avg_row[SHORT_LABELS.get(stat, stat)] = round(sum(vals) / len(vals), 2) if vals else None
        hist_rows.append(avg_row)

        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No historical data available for this course.")


# ---------------------------------------------------------------------------
# Season Results page
# ---------------------------------------------------------------------------
elif page == "🏆 Season Results":
    current_year = date.today().year
    season = st.selectbox("Season", [current_year, current_year - 1, current_year - 2])

    st.title(f"🏆 {season} PGA Tour Season Results")

    results = load_season_results(season)
    if results:
        st.caption(f"{len(results)} tournaments completed")
        rows = []
        for r in results:
            t = r["tournament"]
            w = r["winner"]
            score_str = "—"
            if w and w.par_relative_score is not None:
                score_str = f"{'+' if w.par_relative_score > 0 else ''}{w.par_relative_score}"
            location = ", ".join(filter(None, [t.city, t.state]))
            purse = f"${t.purse / 1_000_000:.1f}M" if t.purse else "—"
            rows.append({
                "Date": t.start_date.strftime("%b %d") if t.start_date else "—",
                "Tournament": t.name,
                "Course": t.course_name,
                "Location": location,
                "Winner": w.player_name if w else "In Progress",
                "Score": score_str,
                "Purse": purse,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No tournament results available for this season.")


# ---------------------------------------------------------------------------
# Custom Rankings page
# ---------------------------------------------------------------------------
elif page == "🎯 Custom Rankings":
    st.title("🎯 Custom Stat Rankings")
    st.caption("Pick the stats you think matter and set your own weights. Players are ranked by a weighted z-score across your selections.")

    current_year = date.today().year
    all_players = load_all_player_stats(current_year)

    if not all_players:
        st.warning("No player stats available. Try refreshing data first.")
        st.stop()

    # Stat selection and weighting
    st.subheader("Select Stats & Weights")
    st.caption("Choose which stats to include and how important each one is (higher = more important).")

    selected_stats = st.multiselect(
        "Stats to include",
        options=list(STAT_LABELS.keys()),
        default=["sg_off_tee", "sg_approach", "sg_putting"],
        format_func=lambda x: STAT_LABELS.get(x, x),
    )

    if not selected_stats:
        st.info("Select at least one stat to generate rankings.")
        st.stop()

    # Weight sliders
    weights = {}
    cols = st.columns(min(len(selected_stats), 4))
    for i, stat in enumerate(selected_stats):
        with cols[i % len(cols)]:
            weights[stat] = st.slider(
                STAT_LABELS[stat],
                min_value=1,
                max_value=10,
                value=5,
                key=f"weight_{stat}",
            )

    # Normalize weights to sum to 1
    total_weight = sum(weights.values())
    norm_weights = {k: v / total_weight for k, v in weights.items()}

    # Show normalized weights
    with st.expander("Your weight distribution"):
        for stat, w in sorted(norm_weights.items(), key=lambda x: x[1], reverse=True):
            st.write(f"{STAT_LABELS[stat]}: **{w*100:.1f}%**")

    st.markdown("---")

    # Compute z-scores and custom composite score
    # First, compute mean/std for each selected stat across all players
    stat_values = {s: [] for s in selected_stats}
    for p in all_players.values():
        for s in selected_stats:
            val = p["stats"].get(s)
            if val is not None:
                stat_values[s].append(val)

    stat_mean_std = {}
    for s in selected_stats:
        vals = stat_values[s]
        if len(vals) > 1:
            mean = sum(vals) / len(vals)
            std = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
            stat_mean_std[s] = (mean, max(std, 0.001))
        elif len(vals) == 1:
            stat_mean_std[s] = (vals[0], 1.0)
        else:
            stat_mean_std[s] = (0.0, 1.0)

    # Score each player
    scored = []
    for pid, pdata in all_players.items():
        # Only include players who have values for at least half the selected stats
        available = sum(1 for s in selected_stats if pdata["stats"].get(s) is not None)
        if available < max(1, len(selected_stats) // 2):
            continue

        custom_score = 0.0
        for s in selected_stats:
            val = pdata["stats"].get(s)
            if val is not None:
                mean, std = stat_mean_std[s]
                z = (val - mean) / std
                custom_score += norm_weights[s] * z

        scored.append({
            "player_name": pdata["player_name"],
            "custom_score": round(custom_score, 4),
            **{s: pdata["stats"].get(s) for s in selected_stats},
            **{f"{s}_rank": pdata["ranks"].get(s) for s in selected_stats},
        })

    scored.sort(key=lambda x: x["custom_score"], reverse=True)

    # Build display table
    st.subheader(f"Rankings ({len(scored)} players)")

    # Player search filter
    search = st.text_input("🔍 Search player", placeholder="Type a name to filter...", key="custom_search")
    display_scored = scored
    if search:
        search_lower = search.lower()
        display_scored = [p for p in scored if search_lower in p["player_name"].lower()]
        st.caption(f"Showing {len(display_scored)} of {len(scored)} players matching \"{search}\"")

    rows = []
    for i, p in enumerate(display_scored, 1):
        row = {
            "#": i,
            "Player": p["player_name"],
            "Custom Score": p["custom_score"],
        }
        for s in selected_stats:
            val = p.get(s)
            rank = p.get(f"{s}_rank")
            label = SHORT_LABELS.get(s, s)
            row[label] = round(val, 2) if val is not None else None
            row[f"{label} Rk"] = rank
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=700,
    )

    # Top 10 visual
    if len(scored) >= 5:
        st.subheader("Top 10 Players")
        top10 = pd.DataFrame(scored[:10])
        fig = px.bar(
            top10,
            x="custom_score",
            y="player_name",
            orientation="h",
            labels={"custom_score": "Custom Score", "player_name": ""},
            color="custom_score",
            color_continuous_scale="Greens",
        )
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            yaxis=dict(autorange="reversed"),
            height=400,
            margin=dict(l=0, r=20, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
