"""Application configuration."""
import os

# PGA Tour GraphQL API
PGA_GRAPHQL_URL = "https://orchestrator.pgatour.com/graphql"
PGA_API_KEY = os.getenv("PGA_API_KEY", "da2-gsrx5bibzbb4njvhl7t37wqyl4")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pga_analysis.db")

# Scheduler
REFRESH_DAY = "tue"  # Tuesday
REFRESH_HOUR = 6
REFRESH_MINUTE = 0
REFRESH_TIMEZONE = "US/Eastern"

# Analysis
MIN_HISTORICAL_SEASONS = 3
DEFAULT_LOOKBACK_SEASONS = 10
RECENCY_HALF_LIFE_WEEKS = 12
HIGHLIGHT_THRESHOLD = 0.5  # standard deviations for highlighting

# Stat categories mapped to PGA Tour stat IDs
STAT_CATEGORIES = {
    # Strokes Gained
    "sg_total": {"name": "SG: Total", "pga_id": "02675"},
    "sg_off_tee": {"name": "SG: Off-the-Tee", "pga_id": "02567"},
    "sg_approach": {"name": "SG: Approach the Green", "pga_id": "02568"},
    "sg_around_green": {"name": "SG: Around-the-Green", "pga_id": "02569"},
    "sg_putting": {"name": "SG: Putting", "pga_id": "02564"},
    "sg_tee_to_green": {"name": "SG: Tee-to-Green", "pga_id": "02674"},
    # Off the Tee
    "driving_distance": {"name": "Driving Distance", "pga_id": "101"},
    "driving_accuracy": {"name": "Driving Accuracy %", "pga_id": "102"},
    "total_driving": {"name": "Total Driving", "pga_id": "129"},
    "club_head_speed": {"name": "Club Head Speed", "pga_id": "02401"},
    "ball_speed": {"name": "Ball Speed", "pga_id": "02402"},
    "good_drive_pct": {"name": "Good Drive %", "pga_id": "02438"},
    # Approach the Green
    "gir": {"name": "Greens in Regulation %", "pga_id": "103"},
    "proximity_to_hole": {"name": "Proximity to Hole", "pga_id": "374"},
    "approach_over_100": {"name": "Approach from > 100 yds", "pga_id": "02437"},
    "approach_inside_100": {"name": "Approach from < 100 yds", "pga_id": "02436"},
    "gir_from_200_plus": {"name": "GIR % from 200+ yds", "pga_id": "077"},
    # Around the Green
    "scrambling": {"name": "Scrambling %", "pga_id": "130"},
    "sand_save_pct": {"name": "Sand Save %", "pga_id": "111"},
    "proximity_arg": {"name": "Proximity to Hole (ARG)", "pga_id": "02590"},
    # Putting
    "putting_avg": {"name": "Putting Average", "pga_id": "104"},
    "putts_per_round": {"name": "Putts Per Round", "pga_id": "119"},
    "one_putt_pct": {"name": "One-Putt %", "pga_id": "413"},
    "three_putt_avoid": {"name": "3-Putt Avoidance", "pga_id": "426"},
    "putting_inside_10": {"name": "Putting Inside 10'", "pga_id": "484"},
    "putting_10_15": {"name": "Putting from 10-15'", "pga_id": "405"},
    "putting_15_20": {"name": "Putting from 15-20'", "pga_id": "406"},
    "putting_over_20": {"name": "Putting from > 20'", "pga_id": "02429"},
    "birdie_conversion": {"name": "Birdie or Better Conversion %", "pga_id": "115"},
    # Scoring
    "birdie_avg": {"name": "Birdie Average", "pga_id": "156"},
    "scoring_avg": {"name": "Scoring Average", "pga_id": "120"},
    "par3_scoring": {"name": "Par 3 Scoring Average", "pga_id": "142"},
    "par4_scoring": {"name": "Par 4 Scoring Average", "pga_id": "143"},
    "par5_scoring": {"name": "Par 5 Scoring Average", "pga_id": "144"},
    "bogey_avoid": {"name": "Bogey Avoidance", "pga_id": "02415"},
    "bounce_back": {"name": "Bounce Back %", "pga_id": "160"},
    "eagles_per_hole": {"name": "Eagles per Hole", "pga_id": "448"},
    # Money / Rankings
    "fedex_pts": {"name": "FedExCup Points", "pga_id": "02671"},
    "top10_finishes": {"name": "Top 10 Finishes", "pga_id": "138"},
}

REQUIRED_STAT_KEYS = [
    "sg_total", "sg_off_tee", "sg_approach", "sg_around_green",
    "sg_putting", "sg_tee_to_green", "driving_distance", "driving_accuracy",
    "gir", "scrambling", "birdie_avg", "scoring_avg",
]

ALL_STAT_KEYS = list(STAT_CATEGORIES.keys())
