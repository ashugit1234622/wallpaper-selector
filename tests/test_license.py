"""Unit tests for license validation and attribution generation."""

from login_wallpaper_selector.providers.license import LicenseValidator


def test_valid_open_licenses():
    valid_examples = [
        "CC0",
        "CC0 1.0 Universal",
        "Public Domain",
        "Public domain",
        "CC BY 4.0",
        "CC BY-SA 3.0",
        "NASA Public Domain",
        "US Government Work",
        "GFDL",
    ]
    for lic in valid_examples:
        assert LicenseValidator.is_valid_license(lic), f"Expected '{lic}' to be recognized as valid"


def test_invalid_and_restricted_licenses():
    invalid_examples = [
        "All Rights Reserved",
        "Copyrighted",
        "Fair use",
        "CC BY-NC 4.0",
        "Non-commercial only",
        "Unknown",
        "",
        None,
    ]
    for lic in invalid_examples:
        assert not LicenseValidator.is_valid_license(lic), f"Expected '{lic}' to be rejected"


def test_attribution_formatting():
    req, attr = LicenseValidator.format_attribution(
        title="<b>Carina Nebula</b>",
        creator="NASA / ESA &amp; Hubble",
        license_name="Public Domain",
        source_url="https://images.nasa.gov/details-PIA123",
    )
    assert req is False
    assert '"Carina Nebula" by NASA / ESA & Hubble' in attr
    assert "https://images.nasa.gov/details-PIA123" in attr

    req_by, attr_by = LicenseValidator.format_attribution(
        title="Mountain Sunset",
        creator="John Doe",
        license_name="CC BY-SA 4.0",
        source_url="https://commons.wikimedia.org/wiki/File:Test.jpg",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
    )
    assert req_by is True
    assert "CC BY-SA 4.0" in attr_by
    assert "https://creativecommons.org/licenses/by-sa/4.0/" in attr_by
