"""Pairwise-comparison ranking engine for hard boulder problems.

Raw comparisons are the source of truth; every ranking here is a pure
function of (problems, comparisons) and can be recomputed at any time.
"""
from .models import Comparison, Problem, Verdict, latest_comparisons
from .scale import GRADE_SEED, grade_to_rating
from .bradley_terry import BradleyTerryConfig, fit_bradley_terry
from .elo import EloConfig, replay_elo
from .winrate import win_rate
from .confidence import confidence
from .result import ProblemRating, RankingResult

__all__ = [
    "Comparison", "Problem", "Verdict", "latest_comparisons",
    "GRADE_SEED", "grade_to_rating",
    "BradleyTerryConfig", "fit_bradley_terry",
    "EloConfig", "replay_elo",
    "win_rate", "confidence",
    "ProblemRating", "RankingResult",
]
