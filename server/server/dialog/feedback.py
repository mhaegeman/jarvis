"""FeedbackLogger — persists one dispatch_log row per turn.

Spec anchor: §8 (learning loop).

After DialogManager.handle_turn finishes:
  1. Session calls feedback.record_turn(turn_id, utterance, explicit,
     plan, rationale, outcome).
  2. Logger writes a dispatch_log row.
  3. Next turn arrives: Session calls feedback.tag_readdress(prior_turn_id,
     other_speaker) if the new turn explicitly addressed the OTHER persona —
     strong negative signal recorded retroactively in the prior row's
     outcome_json.
"""

from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite

from server.dialog.types import Outcome, PersonaId, Plan


class FeedbackLogger:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def record_turn(
        self,
        *,
        turn_id: str,
        utterance: str,
        explicit: PersonaId | None,
        plan: Plan,
        outcome: Outcome,
    ) -> None:
        """Insert (or replace) one row in dispatch_log for this turn."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO dispatch_log "
                "(turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id,
                    time.time(),
                    utterance,
                    explicit,
                    plan.model_dump_json(),
                    plan.rationale,
                    outcome.model_dump_json(),
                ),
            )
            await db.commit()

    async def tag_readdress(
        self,
        *,
        prior_turn_id: str,
        other_speaker: PersonaId,
    ) -> None:
        """Retroactively flag the prior turn as 'user re-addressed the other persona'.

        This is a strong negative signal for the learning loop: the user switched
        to the other persona immediately after this turn, implying dissatisfaction.
        """
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "SELECT outcome_json FROM dispatch_log WHERE turn_id = ?",
                (prior_turn_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return
            outcome = Outcome.model_validate_json(row[0])
            updated = outcome.model_copy(update={"next_turn_readdressed": other_speaker})
            await db.execute(
                "UPDATE dispatch_log SET outcome_json = ? WHERE turn_id = ?",
                (updated.model_dump_json(), prior_turn_id),
            )
            await db.commit()

    async def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return up to `limit` rows from dispatch_log, ordered newest-first."""
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "SELECT turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json "
                "FROM dispatch_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
        return [
            {
                "turn_id": r[0],
                "ts": r[1],
                "utterance": r[2],
                "explicit": r[3],
                "plan": json.loads(r[4]),
                "rationale": r[5],
                "outcome": json.loads(r[6]),
            }
            for r in rows
        ]
