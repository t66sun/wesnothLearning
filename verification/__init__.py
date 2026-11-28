"""Resolve shared drivers used by the retained acceptance records and regression tests."""
from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "verification_support"))
