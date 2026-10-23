"""Unit tests for wallpaper candidate ranking and relevance gate."""

import pytest
from login_wallpaper_selector.core.models import WallpaperCategory, WallpaperCandidate, ColorPalette, WallpaperMood
from login_wallpaper_selector.core.ranking import (
    extract_subject_tokens,
    check_candidate_relevance_gate,
    compute_candidate_quality_score,
    rank_wallpaper_candidates,
)


def _make_candidate(
    title: str,
    width: int = 1920,
    height: int = 1080,
    creator: str = "Artist",
    color: str = "#000000",
    mood: str = "Peaceful",
    download_url: str = "http://example.com/img.jpg",
) -> WallpaperCandidate:
    return WallpaperCandidate(
        id=title.lower().replace(" ", "_"),
        category=WallpaperCategory.SPACE,
        provider_name="test",
        source_url="http://example.com",
        download_url=download_url,
        title=title,
        creator=creator,
        license_name="Public Domain",
        license_url=None,
        attribution_required=False,
        attribution_text=title,
        width=width,
        height=height,
    )


def test_extract_subject_tokens():
    tokens = extract_subject_tokens("The Great Black Hole")
    assert "black" in tokens
    assert "hole" in tokens
    assert "the" not in tokens  # Stopword removed


def test_relevance_gate_passes_matching_subject():
    cand = _make_candidate("Supermassive Black Hole in Deep Space")
    passes = check_candidate_relevance_gate(cand, "Black Hole")
    assert passes is True


def test_relevance_gate_fails_unrelated_subject():
    cand = _make_candidate("Sunny Tropical Beach with Palm Trees")
    passes = check_candidate_relevance_gate(cand, "Black Hole")
    assert passes is False


def test_quality_score_aspect_ratio_match():
    perfect_16_9 = _make_candidate("16:9 Image", width=1920, height=1080)
    score_perfect = compute_candidate_quality_score(perfect_16_9, target_ar=1.778)

    squarish_4_3 = _make_candidate("4:3 Image", width=1600, height=1200)
    score_squarish = compute_candidate_quality_score(squarish_4_3, target_ar=1.778)

    # 16:9 should have higher quality score for 1.778 target display
    assert score_perfect > score_squarish


def test_relevant_1080p_outranks_irrelevant_4k():
    """Ensure an irrelevant 4K image NEVER outranks a relevant 1080p candidate."""
    cand_relevant_1080 = _make_candidate("Magnificent Black Hole Singularity", width=1920, height=1080)
    cand_irrelevant_4k = _make_candidate("Ultra High Definition Sunset on the Beach", width=3840, height=2160)

    ranked = rank_wallpaper_candidates(
        [cand_irrelevant_4k, cand_relevant_1080],
        keyword="Black Hole",
        target_width=1920,
        target_height=1080,
    )

    # Irrelevant candidate fails Stage 1 gate and is filtered out completely
    assert len(ranked) == 1
    assert ranked[0].title == "Magnificent Black Hole Singularity"


def test_ranking_sorts_by_quality_when_all_relevant():
    cand_1080 = _make_candidate("Black Hole 1080p", width=1920, height=1080)
    cand_4k = _make_candidate("Black Hole 4K UHD", width=3840, height=2160)

    ranked = rank_wallpaper_candidates(
        [cand_1080, cand_4k],
        keyword="Black Hole",
        target_width=1920,
        target_height=1080,
    )

    assert len(ranked) == 2
    # 4K relevant outranks 1080p relevant
    assert ranked[0].title == "Black Hole 4K UHD"
    assert ranked[1].title == "Black Hole 1080p"
