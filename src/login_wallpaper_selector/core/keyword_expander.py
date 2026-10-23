"""Intelligent, provider-aware keyword expansion engine preserving core search intent."""

from __future__ import annotations
import re
from typing import List, Optional, Dict
from .models import WallpaperCategory, ColorPalette, WallpaperMood
from .color_analyzer import get_palette_keyword
from .mood_matcher import augment_query_with_mood


# Curated semantic concepts preserving subject intent across tiers (1 to 5)
CURATED_SUBJECT_CONCEPTS: Dict[str, Dict[int, List[str]]] = {
    # ── Space ─────────────────────────────────────────────────────────────
    "black hole": {
        1: ["black hole"],
        2: ["black hole space"],
        3: ["black hole event horizon"],
        4: ["black hole accretion disk"],
        5: ["black hole astronomy"],
    },
    "nebula": {
        1: ["nebula"],
        2: ["nebula deep space"],
        3: ["nebula pillars of creation"],
        4: ["nebula stellar nursery"],
        5: ["nebula cosmic astronomy"],
    },
    "galaxy": {
        1: ["galaxy"],
        2: ["galaxy cosmos"],
        3: ["galaxy spiral starfield"],
        4: ["galaxy cluster deep field"],
        5: ["galaxy astronomy vista"],
    },
    "supernova": {
        1: ["supernova"],
        2: ["supernova remnant space"],
        3: ["supernova explosion starfield"],
        4: ["supernova celestial cosmos"],
        5: ["supernova astronomy"],
    },
    "planet": {
        1: ["planet"],
        2: ["planet space orbit"],
        3: ["planet horizon atmosphere"],
        4: ["planet rings celestial"],
        5: ["planet cosmos solar system"],
    },
    "astronaut": {
        1: ["astronaut"],
        2: ["astronaut space spacewalk"],
        3: ["astronaut earth orbit cosmos"],
        4: ["astronaut floating universe"],
        5: ["astronaut space mission"],
    },

    # ── Nature ────────────────────────────────────────────────────────────
    "waterfall": {
        1: ["waterfall"],
        2: ["waterfall nature landscape"],
        3: ["waterfall forest cascade river"],
        4: ["waterfall mountain canyon"],
        5: ["waterfall scenic wilderness"],
    },
    "waterfalls": {
        1: ["waterfalls"],
        2: ["waterfalls nature landscape"],
        3: ["waterfalls forest cascade river"],
        4: ["waterfalls mountain canyon"],
        5: ["waterfalls scenic wilderness"],
    },
    "mountain": {
        1: ["mountain"],
        2: ["mountain scenic landscape"],
        3: ["mountain alpine peaks dramatic"],
        4: ["mountain misty ridge valley"],
        5: ["mountain wilderness vista"],
    },
    "mountains": {
        1: ["mountains"],
        2: ["mountains scenic landscape"],
        3: ["mountains alpine peaks dramatic"],
        4: ["mountains misty ridge valley"],
        5: ["mountains wilderness vista"],
    },
    "forest": {
        1: ["forest"],
        2: ["forest misty woodland landscape"],
        3: ["forest tall pine trees sunlight"],
        4: ["forest deep wilderness river"],
        5: ["forest nature scenic trail"],
    },
    "ocean": {
        1: ["ocean"],
        2: ["ocean coast cliffs landscape"],
        3: ["ocean dramatic waves horizon"],
        4: ["ocean sunset shoreline vista"],
        5: ["ocean sea water scenic"],
    },
    "aurora": {
        1: ["aurora"],
        2: ["aurora borealis night sky"],
        3: ["aurora northern lights mountains"],
        4: ["aurora night horizon wilderness"],
        5: ["aurora celestial landscape"],
    },
    "desert": {
        1: ["desert"],
        2: ["desert sand dunes landscape"],
        3: ["desert golden hour horizon"],
        4: ["desert wilderness dramatic ridges"],
        5: ["desert scenic arid vista"],
    },

    # ── Art ───────────────────────────────────────────────────────────────
    "cyberpunk": {
        1: ["cyberpunk"],
        2: ["cyberpunk neon city"],
        3: ["cyberpunk futuristic street night"],
        4: ["cyberpunk sci-fi cityscape"],
        5: ["cyberpunk concept art"],
    },
    "renaissance": {
        1: ["renaissance painting"],
        2: ["renaissance fine art oil on canvas"],
        3: ["renaissance classical masterpiece"],
        4: ["renaissance chiaroscuro artwork"],
        5: ["renaissance historical fine art"],
    },
    "impressionism": {
        1: ["impressionism painting"],
        2: ["impressionist fine art landscape"],
        3: ["impressionism oil garden water"],
        4: ["impressionism museum masterpiece"],
        5: ["impressionist classical artwork"],
    },
    "fantasy": {
        1: ["fantasy"],
        2: ["fantasy landscape mythical"],
        3: ["fantasy castle mountains concept art"],
        4: ["fantasy digital painting environment"],
        5: ["fantasy epic adventure vista"],
    },

    # ── Portrait ──────────────────────────────────────────────────────────
    "warrior": {
        1: ["warrior portrait"],
        2: ["warrior character art fantasy"],
        3: ["warrior armored cinematic lighting"],
        4: ["warrior atmospheric character portrait"],
        5: ["warrior dramatic historical figure"],
    },
    "character": {
        1: ["character portrait"],
        2: ["character concept art digital painting"],
        3: ["character expressive dramatic lighting"],
        4: ["character atmospheric portrait"],
        5: ["character fine art figure"],
    },
}


def normalize_keyword(keyword: str) -> str:
    """Clean and standardize search keyword string."""
    if not keyword:
        return ""
    # Strip non-alphanumeric punctuation except hyphens and spaces
    cleaned = re.sub(r"[^\w\s\-]", " ", keyword)
    return " ".join(cleaned.split()).strip()


def find_curated_subject(normalized_keyword: str) -> Optional[str]:
    """Match normalized keyword against curated concepts."""
    lowered = normalized_keyword.lower()
    if lowered in CURATED_SUBJECT_CONCEPTS:
        return lowered
    # Check if keyword contains any curated key as a prominent phrase
    for key in CURATED_SUBJECT_CONCEPTS:
        if key in lowered:
            return key
    return None


def generate_keyword_query_for_tier(
    keyword: str,
    category: WallpaperCategory,
    attempt: int,
    provider_style: str = "general",
    mood: Optional[WallpaperMood] = None,
    color: Optional[ColorPalette] = None,
) -> str:
    """Generate subject-preserving search query tailored for attempt tier (1..5) and provider capability.

    Args:
        keyword: User's raw search keyword.
        category: Selected wallpaper category.
        attempt: Logical search tier index (1 to 5).
        provider_style: Provider query style ("wallpaper", "museum", "scientific", "general").
        mood: Optional mood filter.
        color: Optional color palette filter.

    Returns:
        Synthesized search query retaining the original subject keyword.
    """
    clean_kw = normalize_keyword(keyword)
    if not clean_kw:
        cat_name = category.value.lower() if hasattr(category, "value") else str(category).lower()
        return cat_name

    tier = max(1, min(5, attempt))
    curated_key = find_curated_subject(clean_kw)

    if curated_key:
        # Retrieve tier query preserving curated core subject
        options = CURATED_SUBJECT_CONCEPTS[curated_key].get(tier, [curated_key])
        base_query = options[0]
        # If user entered a broader phrase containing the key (e.g. "futuristic cyberpunk"), preserve user's modifier
        if clean_kw.lower() != curated_key and curated_key in clean_kw.lower():
            prefix = clean_kw.lower().replace(curated_key, "").strip()
            if prefix:
                base_query = f"{prefix} {base_query}"
    else:
        # Generic deterministic expansion preserving core user keyword in EVERY tier
        cat_name = category.value.lower() if hasattr(category, "value") else str(category).lower()
        if tier == 1:
            base_query = clean_kw
        elif tier == 2:
            base_query = f"{clean_kw} {cat_name}"
        elif tier == 3:
            if category == WallpaperCategory.PORTRAIT:
                base_query = f"{clean_kw} portrait character"
            elif category == WallpaperCategory.ART:
                base_query = f"{clean_kw} artwork painting"
            else:
                base_query = f"{clean_kw} landscape"
        elif tier == 4:
            if category == WallpaperCategory.SPACE:
                base_query = f"{clean_kw} deep space vista"
            elif category == WallpaperCategory.PORTRAIT:
                base_query = f"{clean_kw} atmospheric portrait"
            elif category == WallpaperCategory.ART:
                base_query = f"{clean_kw} concept art"
            else:
                base_query = f"{clean_kw} scenic vista"
        else:
            base_query = f"{clean_kw} {cat_name}"

    # ── Provider-Aware Syntax Adaptation ──────────────────────────────────
    # Adapt query to match provider strengths while NEVER dropping the subject
    if provider_style == "wallpaper":
        # Wallpaper aggregators (Wallhaven) benefit from clean terms
        pass
    elif provider_style == "museum":
        # Museum collections (The Met, AIC) - remove noisy terms like 'wallpaper', 'vista'
        unwanted_museum_terms = ["wallpaper", "widescreen", "vista", "scenic"]
        tokens = [t for t in base_query.split() if t.lower() not in unwanted_museum_terms]
        base_query = " ".join(tokens) or clean_kw
    elif provider_style == "scientific":
        # Scientific archives (NASA)
        pass

    # ── Filter Harmonization (Preserving Subject Anchor) ──────────────────
    # Strip contradictory terms from modifiers, but NEVER remove the clean_kw
    contradictory_words = []
    if mood == WallpaperMood.DARK:
        contradictory_words.extend(["vibrant", "radiant", "sunny", "sunlight", "golden hour", "wildflower"])
    if color == ColorPalette.MONOCHROME:
        contradictory_words.extend(["vibrant", "colorful", "rainbow", "wildflower"])

    query_words = base_query.split()
    sanitized_words = []
    clean_kw_tokens = [t.lower() for t in clean_kw.split()]

    for w in query_words:
        # Never strip core subject tokens
        if w.lower() in clean_kw_tokens:
            sanitized_words.append(w)
        elif not any(cw in w.lower() for cw in contradictory_words):
            sanitized_words.append(w)

    base_query = " ".join(sanitized_words) or clean_kw

    # Augment with mood if active and provider is appropriate
    if mood and mood != WallpaperMood.ANY and tier <= 3 and provider_style != "museum":
        base_query = augment_query_with_mood(base_query, mood, category)

    # Augment with color keyword if active and not already present
    if color and color not in (ColorPalette.ANY, ColorPalette.CUSTOM) and tier <= 3:
        pal_kw = "black and white" if color == ColorPalette.MONOCHROME else get_palette_keyword(color)
        if pal_kw and pal_kw.lower() not in base_query.lower():
            base_query = f"{base_query} {pal_kw}"

    return base_query.strip()
