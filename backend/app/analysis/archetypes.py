"""Course archetype classification and fallback weights."""
import logging
from typing import TYPE_CHECKING

from app.config import REQUIRED_STAT_KEYS

if TYPE_CHECKING:
    from app.models import Tournament

logger = logging.getLogger(__name__)

# Predefined archetype weight profiles based on course characteristics
ARCHETYPE_WEIGHTS = {
    "links": {
        "sg_total": 0.10, "sg_off_tee": 0.06, "sg_approach": 0.10,
        "sg_around_green": 0.12, "sg_putting": 0.10, "sg_tee_to_green": 0.08,
        "driving_distance": 0.04, "driving_accuracy": 0.12, "gir": 0.08,
        "scrambling": 0.10, "birdie_avg": 0.05, "scoring_avg": 0.05,
    },
    "parkland_long": {
        "sg_total": 0.10, "sg_off_tee": 0.12, "sg_approach": 0.10,
        "sg_around_green": 0.06, "sg_putting": 0.08, "sg_tee_to_green": 0.10,
        "driving_distance": 0.12, "driving_accuracy": 0.06, "gir": 0.08,
        "scrambling": 0.04, "birdie_avg": 0.08, "scoring_avg": 0.06,
    },
    "parkland_short": {
        "sg_total": 0.10, "sg_off_tee": 0.06, "sg_approach": 0.12,
        "sg_around_green": 0.10, "sg_putting": 0.10, "sg_tee_to_green": 0.08,
        "driving_distance": 0.04, "driving_accuracy": 0.10, "gir": 0.10,
        "scrambling": 0.08, "birdie_avg": 0.06, "scoring_avg": 0.06,
    },
    "desert": {
        "sg_total": 0.10, "sg_off_tee": 0.10, "sg_approach": 0.10,
        "sg_around_green": 0.08, "sg_putting": 0.08, "sg_tee_to_green": 0.10,
        "driving_distance": 0.08, "driving_accuracy": 0.10, "gir": 0.08,
        "scrambling": 0.06, "birdie_avg": 0.06, "scoring_avg": 0.06,
    },
    "coastal": {
        "sg_total": 0.10, "sg_off_tee": 0.08, "sg_approach": 0.10,
        "sg_around_green": 0.10, "sg_putting": 0.08, "sg_tee_to_green": 0.08,
        "driving_distance": 0.06, "driving_accuracy": 0.10, "gir": 0.08,
        "scrambling": 0.10, "birdie_avg": 0.06, "scoring_avg": 0.06,
    },
    "mountain": {
        "sg_total": 0.10, "sg_off_tee": 0.10, "sg_approach": 0.08,
        "sg_around_green": 0.08, "sg_putting": 0.08, "sg_tee_to_green": 0.10,
        "driving_distance": 0.10, "driving_accuracy": 0.08, "gir": 0.08,
        "scrambling": 0.06, "birdie_avg": 0.08, "scoring_avg": 0.06,
    },
}

# State/region to archetype mapping heuristics
DESERT_STATES = {"AZ", "NV"}
COASTAL_STATES = {"HI"}
MOUNTAIN_STATES = {"CO", "UT", "MT", "ID"}
LINKS_KEYWORDS = ["links", "dunes", "seaside", "ocean"]


def classify_course(
    course_name: str = "",
    state: str = "",
    yardage: int = 0,
    par: int = 72,
) -> str:
    """
    Classify a course into an archetype based on metadata.
    Returns one of: links, parkland_long, parkland_short, desert, coastal, mountain
    """
    name_lower = course_name.lower()
    state_upper = (state or "").upper().strip()

    # Check for links-style keywords in course name
    if any(kw in name_lower for kw in LINKS_KEYWORDS):
        return "links"

    if state_upper in DESERT_STATES:
        return "desert"
    if state_upper in COASTAL_STATES:
        return "coastal"
    if state_upper in MOUNTAIN_STATES:
        return "mountain"

    # Parkland classification by yardage
    if yardage and yardage >= 7300:
        return "parkland_long"

    return "parkland_short"


def classify_course_from_tournament(tournament: "Tournament") -> str:
    """Classify a Tournament model instance into an archetype."""
    return classify_course(
        course_name=tournament.course_name or "",
        state=tournament.state or "",
        yardage=tournament.yardage or 0,
        par=tournament.par or 72,
    )


def get_archetype_weights(archetype: str) -> dict[str, float]:
    """
    Get predefined stat weights for a course archetype.

    Returns a new dict with all required stat keys, normalized to sum to 1.0.
    """
    base = ARCHETYPE_WEIGHTS.get(archetype, ARCHETYPE_WEIGHTS["parkland_short"])
    weights = dict(base)
    # Ensure all required keys present
    for key in REQUIRED_STAT_KEYS:
        if key not in weights:
            weights[key] = 0.0
    # Normalize to sum to 1.0
    total = sum(weights[k] for k in REQUIRED_STAT_KEYS)
    if total > 0:
        weights = {k: weights[k] / total for k in REQUIRED_STAT_KEYS}
    else:
        uniform = 1.0 / len(REQUIRED_STAT_KEYS)
        weights = {k: uniform for k in REQUIRED_STAT_KEYS}
    return weights
