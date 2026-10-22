"""Providers package for Login Wallpaper Selector."""
from .base import BaseImageProvider
from .license import LicenseValidator
from .nasa import NasaImageProvider
from .wikimedia import WikimediaCommonsProvider
from .artic import ArtInstituteChicagoProvider
from .wallhaven import WallhavenProvider
from .the_met import TheMetImageProvider
from .bing import BingImageProvider
from .router import ProviderRouter

__all__ = [
    "BaseImageProvider",
    "LicenseValidator",
    "NasaImageProvider",
    "WikimediaCommonsProvider",
    "ArtInstituteChicagoProvider",
    "WallhavenProvider",
    "TheMetImageProvider",
    "BingImageProvider",
    "ProviderRouter",
]
