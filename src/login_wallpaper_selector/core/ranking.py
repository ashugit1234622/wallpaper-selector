"""Candidate ranking and subject-relevance gating engine."""

from __future__ import annotations
import re
from typing import List, Optional, Set
from .models import WallpaperCandidate, ColorPalette, WallpaperMood
from .display import get_native_screen_resolution
from .keyword_expander import normalize_keyword

STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "in", "on", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "of", "off", "over", "under", "again", "further", "then", "once",
}


def extract_subject_tokens(keyword: str) -> List[str]:
    """Extract significant lowercase word tokens from user keyword, ignoring stopwords."""
    cleaned = normalize_keyword(keyword).lower()
    tokens = [w for w in cleaned.split() if len(w) > 1 and w not in STOPWORDS]
    return tokens or [cleaned] if cleaned else []


def check_candidate_relevance_gate(
    candidate: WallpaperCandidate,
    keyword: Optional[str],
) -> bool:
    """Stage 1 Relevance Gate: Verify candidate explicitly matches the search keyword.

    Binary pass/fail check. Irrelevant candidates are disqualified regardless of resolution.
    If keyword is None or empty, all candidates pass (standard category search).
    """
    if not keyword or not keyword.strip():
        return True

    subject_tokens = extract_subject_tokens(keyword)
    if not subject_tokens:
        return True

    clean_kw = normalize_keyword(keyword).lower()
    text_corpus = (candidate.title or "").lower()
    
    # Also check tags if available on candidate
    if hasattr(candidate, "tags") and candidate.tags:
        if isinstance(candidate.tags, list):
            text_corpus += " " + " ".join(t.lower() for t in candidate.tags)
        else:
            text_corpus += " " + str(candidate.tags).lower()

    if hasattr(candidate, "description") and candidate.description:
        text_corpus += " " + str(candidate.description).lower()

    # Exact phrase match in corpus -> automatic pass
    if clean_kw in text_corpus:
        return True

    # Token overlap check: require at least 50% of the significant subject tokens
    matched_tokens = sum(1 for token in subject_tokens if token in text_corpus)
    overlap_ratio = matched_tokens / len(subject_tokens)
    return overlap_ratio >= 0.5


def compute_candidate_quality_score(
    candidate: WallpaperCandidate,
    target_ar: float,
    color_penalty: float = 0.0,
) -> float:
    """Stage 2 Quality Ranking: Compute 0.0 to 100.0 score based on display fit and fidelity."""
    score = 0.0

    # 1. Native Display Aspect Ratio Match (30 pts)
    cand_w = getattr(candidate, "width", 0) or 1920
    cand_h = getattr(candidate, "height", 0) or 1080
    cand_ar = (cand_w / cand_h) if cand_h > 0 else 1.778
    ar_diff = abs(cand_ar - target_ar)
    ar_pts = max(0.0, 30.0 - (ar_diff * 35.0))
    score += ar_pts

    # 2. Resolution Fidelity (30 pts)
    if cand_w >= 3840:
        score += 30.0  # 4K UHD
    elif cand_w >= 2560:
        score += 25.0  # 2K / QHD
    elif cand_w >= 1920:
        score += 18.0  # Full HD
    elif cand_w >= 1280:
        score += 10.0  # 720p HD
    else:
        score += 5.0

    # 3. Aesthetic & Color/Mood Harmony (25 pts)
    harmony_pts = 25.0 * max(0.0, 1.0 - (color_penalty / 3.0))
    score += harmony_pts

    # 4. Metadata Completeness & Source Reliability (15 pts)
    if candidate.title and len(candidate.title) > 3:
        score += 8.0
    if candidate.license_name:
        score += 7.0

    return score


def rank_wallpaper_candidates(
    candidates: List[WallpaperCandidate],
    keyword: Optional[str] = None,
    color: Optional[ColorPalette] = None,
    mood: Optional[WallpaperMood] = None,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
) -> List[WallpaperCandidate]:
    """Filter candidates through Stage 1 Relevance Gate, then sort by Stage 2 Quality Ranking.

    Args:
        candidates: List of retrieved candidates from providers.
        keyword: Optional search keyword.
        color: Optional target palette.
        mood: Optional target mood.
        target_width: Native target screen width (defaults to active monitor).
        target_height: Native target screen height (defaults to active monitor).

    Returns:
        Deduplicated, relevance-filtered, and quality-ranked candidates.
    """
    if not candidates:
        return []

    # Calculate native monitor target aspect ratio dynamically
    if target_width and target_height and target_height > 0:
        target_ar = target_width / target_height
    else:
        sw, sh = get_native_screen_resolution()
        target_ar = (sw / sh) if sh > 0 else 1.778

    # Deduplicate by candidate ID and URL
    seen_ids: Set[str] = set()
    unique_candidates: List[WallpaperCandidate] = []
    for c in candidates:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            unique_candidates.append(c)

    # ── Stage 1: Relevance Gate ───────────────────────────────────────────
    # If a keyword is provided, strictly disqualify candidates that fail relevance
    if keyword and keyword.strip():
        relevant_candidates = [
            c for c in unique_candidates
            if check_candidate_relevance_gate(c, keyword)
        ]
    else:
        relevant_candidates = unique_candidates

    if not relevant_candidates:
        return []

    # ── Stage 2: Quality Ranking ──────────────────────────────────────────
    # Sort remaining relevant candidates by computed quality score
    ranked = sorted(
        relevant_candidates,
        key=lambda c: compute_candidate_quality_score(c, target_ar=target_ar),
        reverse=True,
    )

    return ranked
