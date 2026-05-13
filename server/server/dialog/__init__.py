"""Dialog manager + dispatcher + types.

Phase 1 (foundations) ships types.py and a rule-based dispatcher.
Subsequent phases add manager.py (orchestration), feedback.py (logger),
and profile_refresher.py (learning loop).
"""

from server.dialog.dispatcher import LLMBackedDispatcher, RuleBasedDispatcher
from server.dialog.manager import DialogManager
from server.dialog.types import (
    DialogState,
    Outcome,
    Plan,
    Segment,
    TurnRef,
)

__all__ = [
    "DialogManager",
    "DialogState",
    "LLMBackedDispatcher",
    "Outcome",
    "Plan",
    "RuleBasedDispatcher",
    "Segment",
    "TurnRef",
]
