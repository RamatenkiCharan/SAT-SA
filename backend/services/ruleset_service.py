"""
Ruleset Service.
Central service for loading, caching, registering, activating, and evaluating
versioned analytical rulesets.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from backend.models.ruleset import (
    AnalyticalRuleset,
    DEFAULT_AUTHORITATIVE_RULESET_V1,
)
from backend.repositories.base import BaseSATRepository

logger = logging.getLogger("satsa.rulesets")


class RulesetService:
    """Manages versioned analytical rulesets across repositories and memory caches."""

    @staticmethod
    def get_fallback_ruleset() -> AnalyticalRuleset:
        """Returns the frozen authoritative SRS v2.0 baseline ruleset."""
        return DEFAULT_AUTHORITATIVE_RULESET_V1

    @classmethod
    def get_active_ruleset(cls, repo: Optional[BaseSATRepository] = None) -> AnalyticalRuleset:
        """
        Retrieves the currently active analytical ruleset.
        Falls back explicitly and safely to the authoritative baseline ruleset if no active ruleset is stored.
        """
        if repo is not None:
            try:
                active = repo.get_active_ruleset()
                if active is not None:
                    return active
            except Exception as e:
                logger.warning(f"Failed to fetch active ruleset from repository: {e}. Falling back to default V1.")

        return cls.get_fallback_ruleset()

    @classmethod
    def get_ruleset_by_version(
        cls,
        version: str,
        repo: Optional[BaseSATRepository] = None,
    ) -> AnalyticalRuleset:
        """
        Retrieves a specific ruleset by version string (e.g. 'V1', 'V2-EXPERIMENTAL').
        If not found, raises ValueError (or returns fallback if version matches V1).
        """
        if version == DEFAULT_AUTHORITATIVE_RULESET_V1.version:
            if repo is not None:
                try:
                    stored = repo.get_ruleset_by_version(version)
                    if stored is not None:
                        return stored
                except Exception:
                    pass
            return cls.get_fallback_ruleset()

        if repo is not None:
            stored = repo.get_ruleset_by_version(version)
            if stored is not None:
                return stored

        raise ValueError(f"Analytical ruleset version '{version}' not found.")

    @classmethod
    def list_rulesets(cls, repo: Optional[BaseSATRepository] = None) -> list[AnalyticalRuleset]:
        """Lists all registered versioned rulesets."""
        if repo is not None:
            try:
                stored_list = repo.list_rulesets()
                if stored_list:
                    return stored_list
            except Exception as e:
                logger.warning(f"Failed to list rulesets from repository: {e}.")

        return [cls.get_fallback_ruleset()]

    @classmethod
    def register_ruleset(
        cls,
        ruleset: AnalyticalRuleset,
        set_active: bool = False,
        repo: Optional[BaseSATRepository] = None,
    ) -> AnalyticalRuleset:
        """Registers a new versioned ruleset in the repository."""
        if repo is not None:
            return repo.register_ruleset(ruleset, set_active=set_active)
        return ruleset

    @classmethod
    def activate_ruleset(
        cls,
        version: str,
        repo: Optional[BaseSATRepository] = None,
    ) -> AnalyticalRuleset:
        """Switches the active ruleset to the specified version."""
        if repo is not None:
            return repo.set_active_ruleset(version)
        if version == DEFAULT_AUTHORITATIVE_RULESET_V1.version:
            return DEFAULT_AUTHORITATIVE_RULESET_V1
        raise ValueError(f"Cannot activate ruleset '{version}': repository not attached.")
