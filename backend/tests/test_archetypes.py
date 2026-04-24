"""Tests for course archetype classification and fallback weights."""
import pytest
from unittest.mock import MagicMock

from app.config import REQUIRED_STAT_KEYS, MIN_HISTORICAL_SEASONS
from app.analysis.archetypes import (
    classify_course,
    classify_course_from_tournament,
    get_archetype_weights,
    ARCHETYPE_WEIGHTS,
)


class TestClassifyCourse:
    def test_links_keyword_in_name(self):
        assert classify_course(course_name="Ocean Links Golf Club") == "links"

    def test_links_dunes_keyword(self):
        assert classify_course(course_name="Sand Dunes Resort") == "links"

    def test_links_seaside_keyword(self):
        assert classify_course(course_name="Seaside Course") == "links"

    def test_desert_state_az(self):
        assert classify_course(course_name="TPC Scottsdale", state="AZ") == "desert"

    def test_desert_state_nv(self):
        assert classify_course(course_name="Some Course", state="NV") == "desert"

    def test_coastal_state_hi(self):
        assert classify_course(course_name="Kapalua", state="HI") == "coastal"

    def test_mountain_state_co(self):
        assert classify_course(course_name="Castle Pines", state="CO") == "mountain"

    def test_mountain_state_ut(self):
        assert classify_course(course_name="Some Course", state="UT") == "mountain"

    def test_parkland_long_by_yardage(self):
        assert classify_course(course_name="TPC Sawgrass", state="FL", yardage=7400) == "parkland_long"

    def test_parkland_short_default(self):
        assert classify_course(course_name="Augusta National", state="GA", yardage=7200) == "parkland_short"

    def test_parkland_short_no_yardage(self):
        assert classify_course(course_name="Some Course", state="GA") == "parkland_short"

    def test_links_takes_priority_over_state(self):
        """Links keyword in name should override state-based classification."""
        assert classify_course(course_name="Desert Links", state="AZ") == "links"

    def test_case_insensitive_course_name(self):
        assert classify_course(course_name="OCEAN LINKS") == "links"

    def test_state_case_insensitive(self):
        assert classify_course(course_name="Some Course", state="az") == "desert"


class TestClassifyCourseFromTournament:
    def test_with_tournament_model(self):
        tournament = MagicMock()
        tournament.course_name = "TPC Scottsdale"
        tournament.state = "AZ"
        tournament.yardage = 7200
        tournament.par = 71
        result = classify_course_from_tournament(tournament)
        assert result == "desert"

    def test_with_none_fields(self):
        tournament = MagicMock()
        tournament.course_name = None
        tournament.state = None
        tournament.yardage = None
        tournament.par = None
        result = classify_course_from_tournament(tournament)
        assert result == "parkland_short"


class TestGetArchetypeWeights:
    @pytest.mark.parametrize("archetype", list(ARCHETYPE_WEIGHTS.keys()))
    def test_weights_sum_to_one(self, archetype):
        weights = get_archetype_weights(archetype)
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"{archetype} weights sum to {total}"

    @pytest.mark.parametrize("archetype", list(ARCHETYPE_WEIGHTS.keys()))
    def test_all_required_keys_present(self, archetype):
        weights = get_archetype_weights(archetype)
        for key in REQUIRED_STAT_KEYS:
            assert key in weights, f"Missing {key} in {archetype}"

    @pytest.mark.parametrize("archetype", list(ARCHETYPE_WEIGHTS.keys()))
    def test_weights_non_negative(self, archetype):
        weights = get_archetype_weights(archetype)
        for key, val in weights.items():
            assert val >= 0.0, f"{key} in {archetype} is negative: {val}"

    def test_unknown_archetype_falls_back(self):
        weights = get_archetype_weights("nonexistent")
        expected = get_archetype_weights("parkland_short")
        for key in REQUIRED_STAT_KEYS:
            assert abs(weights[key] - expected[key]) < 0.001

    def test_different_archetypes_have_different_weights(self):
        links = get_archetype_weights("links")
        desert = get_archetype_weights("desert")
        # At least some weights should differ
        diffs = [abs(links[k] - desert[k]) for k in REQUIRED_STAT_KEYS]
        assert max(diffs) > 0.001
