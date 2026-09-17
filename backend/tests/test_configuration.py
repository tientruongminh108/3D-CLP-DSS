import pytest
from app.config import get_settings
from app.core.models import RunOptions


class TestConfigurationDefaults:
    """Tests for configuration defaults (Section 3 - CFG-01 to CFG-05)"""

    def test_CFG_01_defaults_match_guide(self):
        """CFG-01: Defaults match Section 7 table exactly"""
        settings = get_settings()
        assert settings.POPULATION_SIZE == 60
        assert settings.GENERATIONS == 100
        assert settings.TOLERANCE_GAP_CM == 2.0
        assert settings.FITNESS_COG_PENALTY_WEIGHT == 0.3

    def test_CFG_02_cog_penalty_weight_bound(self):
        """CFG-02: cog_penalty_weight should stay < Unplaced rank weight / 3 (~0.67)"""
        settings = get_settings()
        unplaced_rank_weight = settings.UNPLACED_RANK_WEIGHT
        max_allowed = unplaced_rank_weight / 3
        assert settings.FITNESS_COG_PENALTY_WEIGHT < max_allowed

    def test_CFG_03_tolerance_gap_zero_accepted(self):
        """CFG-03: tolerance_gap_cm = 0 should be accepted as explicit value"""
        options = RunOptions(tolerance_gap_cm=0.0)
        assert options.tolerance_gap_cm == 0.0

    def test_CFG_04_all_defaults_enumerated(self):
        """CFG-04: All defaults enumerated in one place"""
        settings = get_settings()
        defaults = {
            "POPULATION_SIZE": 60,
            "GENERATIONS": 100,
            "TOLERANCE_GAP_CM": 2.0,
            "FITNESS_COG_PENALTY_WEIGHT": 0.3,
            "UNPLACED_RANK_WEIGHT": 2.0,
            "FITNESS_VOLUME_WEIGHT": 1.0,
            "SUPPORT_RATIO": 0.8,
            "CONTACT_RATIO_WEIGHT": 1.0,
            "RESIDUAL_VOLUME_WEIGHT": 1.0,
            "MAX_WEIGHT_UTILIZATION": 1.0,
            "COG_TOLERANCE_XY": 0.05,
            "COG_TOLERANCE_Z": 0.10,
        }
        for key, expected in defaults.items():
            assert getattr(settings, key) == expected, f"{key} mismatch: got {getattr(settings, key)}, expected {expected}"

    def test_CFG_05_override_takes_effect(self):
        """CFG-05: Override takes effect for single parameter"""
        options = RunOptions(
            population_size=50,
            generations=60,
            tolerance_gap_cm=1.0,
        )
        assert options.population_size == 50
        assert options.generations == 60
        assert options.tolerance_gap_cm == 1.0