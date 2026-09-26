from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "3D Container Loading DSS"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # Solver Parameters (Section 7)
    # Genetic Algorithm
    POPULATION_SIZE: int = 60
    GENERATIONS: int = 100
    ELITE_FRACTION: float = 0.10
    MUTATION_RATE_BASE: float = 0.25
    MUTATION_RATE_MAX: float = 0.50
    MUTATION_RATE_MIN: float = 0.10
    CROSSOVER_PROBABILITY: float = 0.7
    MIN_IMPROVEMENT: float = 0.01
    EARLY_STOP_PATIENCE: int = 60

    # Simulated Annealing (embedded in GA)
    SA_INTERVAL_GENERATIONS: int = 5
    SA_INITIAL_TEMP: float = 100.0
    SA_MIN_TEMP: float = 1.0
    SA_COOLING_RATE: float = 0.9

    # Block Generation
    MIN_BLOCK_FILL_RATIO: float = 0.75
    MAX_BLOCK_FRACTION_X: float = 0.20  # GA search cap — length/X axis (unchanged)
    MAX_BLOCK_FRACTION_Y: float = 0.70  # GA search cap — width/Y axis (allows 2-3 carton layers)
    MAX_BLOCK_FRACTION_Z: float = 0.70 # GA search cap — height/Z axis (allows 2-3 carton tiers)
    MAX_BLOCK_FRACTION_REPORT: float = 0.50  # Report/visual cap (>= search cap)
    SIMILAR_SIZE_TOLERANCE: float = 0.1

    # Placement Strategy
    TOLERANCE_GAP_CM: float = 2.0
    SUPPORT_RATIO: float = 0.6
    CONTACT_RATIO_WEIGHT: float = 1.0
    RESIDUAL_VOLUME_WEIGHT: float = 1.0

    # Constraints
    MAX_WEIGHT_UTILIZATION: float = 1.0
    COG_TOLERANCE_XY: float = 0.05  # ±5% of length/width
    COG_TOLERANCE_Z: float = 0.10   # +10% of height
    UNPLACED_RANK_WEIGHT: float = 2.0

    # Fitness weights
    FITNESS_VOLUME_WEIGHT: float = 1.0
    FITNESS_COG_PENALTY_WEIGHT: float = 0.3  # cog_weight
    # INFEASIBLE_PENALTY computed per run

    # Default container (used if none selected)
    DEFAULT_CONTAINER_TYPE: str = "40HC"
    DEFAULT_CONTAINER_LENGTH: float = 1203.2
    DEFAULT_CONTAINER_WIDTH: float = 235.2
    DEFAULT_CONTAINER_HEIGHT: float = 270.0
    DEFAULT_CONTAINER_MAX_WEIGHT: float = 28000.0

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()