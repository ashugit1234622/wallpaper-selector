"""Dynamic Time-of-Day wallpaper themes and curated keyword routing.

Provides 4 distinct thematic time slots:
1. Morning (7 AM - 11 AM): Bright, happy, encouraging
2. Midday (11 AM - 2 PM): Warm, natural, peaceful
3. Afternoon (2 PM - 6 PM): Space, exploration, fantasy, wonder
4. Evening and Night (6 PM - 7 AM): Dark, horror, creepy, atmospheric
"""

from __future__ import annotations
import random
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple


class TimeOfDaySlot(str, Enum):
    MORNING = "Morning"
    MIDDAY = "Midday"
    AFTERNOON = "Afternoon"
    NIGHT = "Evening and Night"


TIME_OF_DAY_THEMES: dict[TimeOfDaySlot, str] = {
    TimeOfDaySlot.MORNING: "Bright, happy, encouraging",
    TimeOfDaySlot.MIDDAY: "Warm, natural, peaceful",
    TimeOfDaySlot.AFTERNOON: "Space, exploration, fantasy, wonder",
    TimeOfDaySlot.NIGHT: "Dark, horror, creepy, atmospheric",
}

TIME_OF_DAY_KEYWORDS: dict[TimeOfDaySlot, List[str]] = {
    TimeOfDaySlot.MORNING: [
        "Sunrise", "Sunshine", "Flowers", "Nature", "Mountains",
        "Beach", "Blue Sky", "Rainbow", "Spring", "Birds",
        "Garden", "Green", "Colorful", "Happy", "Bright",
        "Morning", "Sunset", "Butterflies", "Lake", "Happiness",
    ],
    TimeOfDaySlot.MIDDAY: [
        "Forest", "Trees", "Waterfall", "Ocean", "River",
        "Mountains", "Wildlife", "Flowers", "Nature", "Lake",
        "Green", "Desert", "Beach", "Garden", "Sunlight",
        "Earth", "Jungle", "Animals", "Landscape", "Tropical",
    ],
    TimeOfDaySlot.AFTERNOON: [
        "Space", "Galaxy", "Nebula", "Planets", "Stars",
        "Moon", "Saturn", "Astronaut", "Earth", "Universe",
        "Cosmos", "Rocket", "Astronomy", "Sci-Fi", "Cyberpunk",
        "Fantasy", "Robots", "Futuristic", "Aliens", "Comet",
    ],
    TimeOfDaySlot.NIGHT: [
        "Dark", "Horror", "Creepy", "Ghost", "Haunted",
        "Scary", "Night", "Moonlight", "Fog", "Castle",
        "Skull", "Gothic", "Shadow", "Raven", "Bats",
        "Cemetery", "Vampire", "Zombie", "Abandoned", "Mystery",
        "Monster", "Skeleton", "Witch", "Demon", "Graveyard",
        "Storm", "Eerie", "Halloween", "Darkness", "Nightmare",
    ],
}


def get_current_time_of_day_slot(dt: Optional[datetime] = None) -> TimeOfDaySlot:
    """Determine the time-of-day slot based on local system time.

    Hours mapping:
    - 7:00 AM to 10:59 AM (7 <= hour < 11) -> Morning
    - 11:00 AM to 1:59 PM (11 <= hour < 14) -> Midday
    - 2:00 PM to 5:59 PM (14 <= hour < 18) -> Afternoon
    - 6:00 PM to 6:59 AM (hour >= 18 or hour < 7) -> Evening and Night
    """
    if dt is None:
        dt = datetime.now()

    hour = dt.hour
    if 7 <= hour < 11:
        return TimeOfDaySlot.MORNING
    elif 11 <= hour < 14:
        return TimeOfDaySlot.MIDDAY
    elif 14 <= hour < 18:
        return TimeOfDaySlot.AFTERNOON
    else:
        return TimeOfDaySlot.NIGHT


def get_time_of_day_keywords(slot: TimeOfDaySlot) -> List[str]:
    """Retrieve the curated list of independent search terms for a given time slot."""
    return list(TIME_OF_DAY_KEYWORDS.get(slot, []))


def select_time_of_day_keywords(
    slot: TimeOfDaySlot,
    recent_keywords: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Select a primary keyword and an alternative fallback keyword for the time slot.

    Avoids recently used keywords to ensure variety across rotations.
    Always treats each keyword as a single independent search term.
    """
    all_keywords = get_time_of_day_keywords(slot)
    if not all_keywords:
        return "Nature", "Landscape"

    recent_set = {k.strip().lower() for k in (recent_keywords or [])}
    # Filter candidates not recently used
    fresh_candidates = [k for k in all_keywords if k.strip().lower() not in recent_set]
    if len(fresh_candidates) < 2:
        fresh_candidates = list(all_keywords)

    random.shuffle(fresh_candidates)
    primary = fresh_candidates[0]
    fallback = fresh_candidates[1] if len(fresh_candidates) > 1 else (
        random.choice([k for k in all_keywords if k != primary]) if len(all_keywords) > 1 else primary
    )

    return primary, fallback
