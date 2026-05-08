"""Frozen dataclasses used at the memory-package boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    id: int
    session_id: str
    ts: str
    role: str
    content: str


@dataclass(frozen=True)
class Fact:
    key: str
    value: str


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    started_at: str
    ended_at: str | None
    summary: str


@dataclass(frozen=True)
class RecentSummaryMeta:
    summary: str
    refreshed_at: str
    last_turn_id: int
