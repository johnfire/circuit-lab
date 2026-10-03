"""Shared theme tokens keep both pages readable and the brand consistent."""

import re
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[1]
THEME = dict(re.findall(r'--color-([\w-]+): (#[0-9a-f]{6});',
                       (ROOT / 'frontend/public/theme.css').read_text()))


def calculate_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear_channels = [channel / 12.92 if channel <= 0.04045
                       else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return sum(channel * weight for channel, weight in
               zip(linear_channels, (0.2126, 0.7152, 0.0722), strict=True))


def calculate_contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((calculate_luminance(foreground),
                             calculate_luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_calculation_reference_colors() -> None:
    assert calculate_luminance('#000000') == 0
    assert calculate_luminance('#ffffff') == 1
    assert calculate_contrast('#000000', '#ffffff') == 21
    assert calculate_contrast('#ffffff', '#ffffff') == 1


@pytest.mark.parametrize('foreground', ['text', 'muted', 'heading'])
@pytest.mark.parametrize('background', ['background', 'surface', 'raised', 'warning-surface'])
def test_all_theme_text_meets_aa_contrast(foreground: str, background: str) -> None:
    assert calculate_contrast(THEME[foreground], THEME[background]) >= 4.5


@pytest.mark.parametrize('background', ['accent', 'accent-hover'])
def test_primary_button_text_meets_aa_contrast(background: str) -> None:
    assert calculate_contrast(THEME['on-accent'], THEME[background]) >= 4.5


@pytest.mark.parametrize('foreground', ['control-border', 'focus', 'signal-0',
                                      'signal-1', 'signal-2'])
@pytest.mark.parametrize('background', ['background', 'surface'])
def test_controls_and_chart_traces_meet_nontext_contrast(foreground: str,
                                                       background: str) -> None:
    assert calculate_contrast(THEME[foreground], THEME[background]) >= 3


@pytest.mark.parametrize('page', ['frontend/index.html', 'frontend/public/landing.html'])
def test_both_pages_load_shared_theme_and_matching_browser_color(page: str) -> None:
    markup = (ROOT / page).read_text()
    assert '<link rel="stylesheet" href="/theme.css" />' in markup
    assert f'<meta name="theme-color" content="{THEME["background"]}" />' in markup


def test_favicon_matches_shared_brand_palette() -> None:
    icon = ElementTree.fromstring((ROOT / 'frontend/public/favicon.svg').read_text())
    namespace = '{http://www.w3.org/2000/svg}'
    background = icon.find(namespace + 'rect')
    initials = icon.find(namespace + 'path')
    assert background is not None and initials is not None
    assert background.attrib['fill'] == THEME['background']
    assert initials.attrib['stroke'] == THEME['heading']
