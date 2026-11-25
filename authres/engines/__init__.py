"""Engine implementations and the neutral adapter contract.

``contract.py`` contains the neutral types a future external adapter must
satisfy. ``index_engine.py`` is Engine B, an in-project implementation written
from ``docs/policy-semantics.md`` with a dictionary-index evaluation strategy.
Engine B is not an external authorization engine and is not independently
validated.
"""

from authres.engines.contract import EngineAdapter, EngineOutcome, EngineStatus
from authres.engines.index_engine import IndexEngine

__all__ = ["EngineAdapter", "EngineOutcome", "EngineStatus", "IndexEngine"]
