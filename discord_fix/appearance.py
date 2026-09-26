"""Accessible color themes and display-setting validation helpers."""

PALETTES = {
    "light": {
        "background": "#eef2f5",
        "surface": "#ffffff",
        "foreground": "#172126",
        "muted": "#53636d",
        "accent": "#1769aa",
        "accent_text": "#ffffff",
    },
    "ash": {
        "background": "#313338",
        "surface": "#2b2d31",
        "foreground": "#f2f3f5",
        "muted": "#c4c9d0",
        "accent": "#4752c4",
        "accent_text": "#ffffff",
    },
    "dark": {
        "background": "#1e1f22",
        "surface": "#2b2d31",
        "foreground": "#f2f3f5",
        "muted": "#b5bac1",
        "accent": "#4752c4",
        "accent_text": "#ffffff",
    },
    "onyx": {
        "background": "#000000",
        "surface": "#0b0b0d",
        "foreground": "#f5f5f7",
        "muted": "#c2c2c8",
        "accent": "#8ea1ff",
        "accent_text": "#000000",
    },
}


def palette_for(theme, high_contrast=False):
    """Return a fresh palette for a supported theme or high contrast mode."""
    if high_contrast:
        return {
            "background": "#000000",
            "surface": "#000000",
            "foreground": "#ffffff",
            "muted": "#dddddd",
            "accent": "#ffff00",
            "accent_text": "#000000",
        }
    try:
        return PALETTES[theme].copy()
    except KeyError as exc:
        raise ValueError("Kies een beschikbaar kleurthema.") from exc


def contrast_ratio(foreground, background):
    """Calculate WCAG relative-luminance contrast for two #RRGGBB colors."""

    def luminance(color):
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return sum(
            weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
        )

    first, second = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)
