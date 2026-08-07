"""The Consistency Validator (docs/design/phase-2d/02-personality-engine.md
Sec4) -- rule-based, deterministic, no model call (Sec0.3). Four check
families, each traceable to a specific Doc 23 section. Per design doc Sec8:
checks 2 (forbidden pattern) and 3 (emotional stability) are hard stops
(`passed=False`); checks 1 (confidence-language) and 4 (professionalism
floor) are soft corrections (`passed=True`, `adjusted_content` set).

Pattern sets are intentionally small and explicit, not a general content
classifier -- this is a structural check against a fixed, named list of
forbidden behaviors (Doc 23 Sec6), not a judgment call requiring
intelligence (Sec0.3's core design commitment).
"""

from __future__ import annotations

import re

from nova_personality_engine.domain.models import (
    ConfidenceTier,
    ValidationResult,
    ViolationCheckFamily,
    ViolationRecord,
)

__all__ = ["validate"]

# --- Check 1: confidence-language consistency (Doc 23 Sec5.2, Sec2 Trust
# Before Intelligence) -- soft correction. Only overclaiming is corrected,
# never underclaiming (design doc Sec4.1).
_OVERCLAIM_PATTERN = re.compile(
    r"\b(definitely|certainly|guarantee(d)?|100%|without a doubt|absolutely|"
    r"always works|never fails|I'?m (certain|sure)|no question)\b",
    re.IGNORECASE,
)

# --- Check 2: forbidden-pattern matching (Doc 23 Sec6) -- hard stop.
_FORBIDDEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "manufactured_urgency": re.compile(
        r"\b(act now|hurry|don'?t wait|limited time|last chance|before it'?s too late)\b",
        re.IGNORECASE,
    ),
    "guilt_inducing": re.compile(
        r"\b(you should feel bad|it'?s your fault|you'?ll regret|disappoint(ed)? (me|us))\b",
        re.IGNORECASE,
    ),
    "fabricated_shared_feeling": re.compile(
        r"\bi (understand|know) (exactly )?how you feel\b", re.IGNORECASE
    ),
}

# --- Check 3: emotional stability markers (Doc 23 Sec4.6 standing
# directive) -- hard stop.
_EMOTIONAL_INSTABILITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "dismissive": re.compile(
        r"\b(obviously|clearly you|as I already (said|explained)|if you had (read|listened))\b",
        re.IGNORECASE,
    ),
    "defensive": re.compile(
        r"\b(that'?s not my fault|I never said that|you'?re wrong about what I said)\b",
        re.IGNORECASE,
    ),
}

# --- Check 4: professionalism floor (Doc 23 Sec9) -- soft correction.
_SHOUTED_WORD_PATTERN = re.compile(r"\b[A-Z]{4,}\b")
_EXCESS_EXCLAMATION_PATTERN = re.compile(r"!{2,}")


def _check_confidence_language(
    content: str, confidence_tier: ConfidenceTier
) -> tuple[str | None, ViolationRecord | None]:
    if confidence_tier not in (ConfidenceTier.LOW, ConfidenceTier.UNKNOWN):
        return None, None
    if not _OVERCLAIM_PATTERN.search(content):
        return None, None
    adjusted = f"I'm not fully certain, but: {content}"
    return adjusted, ViolationRecord(
        check_family=ViolationCheckFamily.CONFIDENCE_LANGUAGE,
        detail=(
            f"Content used unhedged, confident phrasing while confidence_tier="
            f"{confidence_tier.value!r}; a hedging prefix was applied."
        ),
    )


def _check_forbidden_patterns(content: str) -> ViolationRecord | None:
    for name, pattern in _FORBIDDEN_PATTERNS.items():
        if pattern.search(content):
            return ViolationRecord(
                check_family=ViolationCheckFamily.FORBIDDEN_PATTERN,
                detail=f"Matched forbidden pattern {name!r} (Doc 23 Sec6).",
            )
    return None


def _check_emotional_stability(content: str) -> ViolationRecord | None:
    for name, pattern in _EMOTIONAL_INSTABILITY_PATTERNS.items():
        if pattern.search(content):
            return ViolationRecord(
                check_family=ViolationCheckFamily.EMOTIONAL_STABILITY,
                detail=f"Matched emotional-instability pattern {name!r} (Doc 23 Sec4.6).",
            )
    return None


def _check_professionalism_floor(content: str) -> tuple[str | None, ViolationRecord | None]:
    shouted = _SHOUTED_WORD_PATTERN.search(content)
    excess_exclaim = _EXCESS_EXCLAMATION_PATTERN.search(content)
    if shouted is None and excess_exclaim is None:
        return None, None
    adjusted = content
    if shouted is not None:
        adjusted = _SHOUTED_WORD_PATTERN.sub(lambda m: m.group(0).capitalize(), adjusted)
    if excess_exclaim is not None:
        adjusted = _EXCESS_EXCLAMATION_PATTERN.sub("!", adjusted)
    return adjusted, ViolationRecord(
        check_family=ViolationCheckFamily.PROFESSIONALISM_FLOOR,
        detail="Content used shouted formatting (all-caps word or repeated exclamation marks).",
    )


def validate(content: str, *, confidence_tier: ConfidenceTier) -> ValidationResult:
    """Design doc Sec4. Runs all four checks; hard-stop violations
    (forbidden pattern, emotional stability) short-circuit with
    `passed=False` and no adjusted content -- delivering an ethics-violating
    response, even adjusted, is worse than the interruption cost of a
    delay (design doc Sec8)."""
    violations: list[ViolationRecord] = []

    forbidden = _check_forbidden_patterns(content)
    if forbidden is not None:
        violations.append(forbidden)
    instability = _check_emotional_stability(content)
    if instability is not None:
        violations.append(instability)
    if violations:
        return ValidationResult(passed=False, adjusted_content=None, violations=violations)

    adjusted = content
    confidence_adjusted, confidence_violation = _check_confidence_language(
        adjusted, confidence_tier
    )
    if confidence_violation is not None:
        violations.append(confidence_violation)
        adjusted = confidence_adjusted or adjusted

    professionalism_adjusted, professionalism_violation = _check_professionalism_floor(adjusted)
    if professionalism_violation is not None:
        violations.append(professionalism_violation)
        adjusted = professionalism_adjusted or adjusted

    return ValidationResult(
        passed=True,
        adjusted_content=adjusted if adjusted != content else None,
        violations=violations,
    )
