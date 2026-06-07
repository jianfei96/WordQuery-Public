# WordQuery for Anki 25+

[中文说明](README-CN.md)

A modernized fork of [WordQuery](https://github.com/finalion/WordQuery) for **Anki 25.x** (Python 3.13, PyQt6, Qt 6).

## What's New

- **Anki 25.x support** — fully ported from Python 2/PyQt4 to Python 3.13/PyQt6
- **Pluggable dictionary parsers** — field extraction for specific MDX dictionaries is now modular; add your own parser by dropping a `.py` file in `parsers/`
- **Audio extraction** — extracts audio from MDD resources, with automatic SPX/OGG → MP3 conversion via ffmpeg
- **MDD key caching** — caches the full MDD key map on first access for fast repeated lookups
- **Cross-platform ffmpeg detection** — auto-finds ffmpeg on macOS (Homebrew), Linux, and Windows; configurable via Settings

## Requirements

- Anki 25.x (tested on 25.09.4)
- macOS / Linux / Windows
- **ffmpeg** (optional, for SPX/OGG audio conversion)

## Installation

1. Download or clone this repository
2. Copy the contents into your Anki addons folder:
   - macOS: `~/Library/Application Support/Anki2/addons21/WordQuery/`
   - Windows: `%APPDATA%\Anki2\addons21\WordQuery\`
   - Linux: `~/.local/share/Anki2/addons21/WordQuery/`
3. Restart Anki

## Usage

### Set Dictionary Folders

1. Tools → WordQuery → Options
2. Click "Dict folders", add folders containing `.mdx`/`.ifo` files
3. Check "Export media files" if you want audio extracted

### Configure Note Type Mapping

1. Click "Choose note type"
2. Select the word field (radio button)
3. Map each note field to a dictionary field

### Query Words

- **Editor**: Click "Query" button or right-click → WordQuery
- **Browser**: Select words → WordQuery → Query selected
- **Shortcut**: `Ctrl+Q` (configurable)

## Dictionary Parsers

WordQuery uses a pluggable parser system for field extraction from MDX dictionaries. The `default` field (full HTML) works with **any** MDX dictionary. Additional fields (headword, phonetic, POS, definition, example, audio) require a matching parser.

### Included Parsers

| Parser | Dictionary | Fields |
|--------|-----------|--------|
| `oxford_primary.py` | oxfordPrimary bilingual | headword, phonetic, pos, pos_cn, definition, example |
| `mw11sound.py` | Merriam-Webster 11th Collegiate | headword, phonetic, pos, definition |

### Adding a New Parser

1. Create a `.py` file in `src/service/parsers/`
2. Subclass `DictParser`
3. Implement `match()` to identify your dictionary
4. Implement the field methods you need

```python
# src/service/parsers/mydict.py
import re
from .base import DictParser

class MyDictParser(DictParser):
    @staticmethod
    def match(title, filename):
        return 'mydict' in (title or '').lower()

    def fld_headword(self, raw_html):
        m = re.search(r'<b>(.*?)</b>', raw_html)
        return m.group(1) if m else ''

    def fld_definition(self, raw_html):
        # your extraction logic
        return ''
```

The parser is auto-discovered at runtime — no registration needed.

### Audio Support

The `audio` field works with any MDX dictionary that contains `sound:` links in its HTML. Supported formats:
- **MP3/WAV** — extracted directly
- **SPX/OGG** — auto-converted to MP3 via ffmpeg

If ffmpeg is not found, SPX/OGG files will be extracted but not converted.

## ffmpeg Configuration

WordQuery auto-detects ffmpeg in:
- macOS: `/opt/homebrew/bin/ffmpeg`, `/usr/local/bin/ffmpeg`
- Linux: `/usr/bin/ffmpeg`, `/usr/local/bin/ffmpeg`
- Windows: `Program Files\ffmpeg\bin\ffmpeg.exe`
- System PATH

To set a custom path: Tools → WordQuery → Options → Settings → ffmpeg path

## Web Dictionary Services

The original web services (Youdao, Bing, ICIBA, etc.) are included. See `src/service/` for available services. You can create custom web services by subclassing `WebService`.

## Credits

- Original author: [Liang Feng (finalion)](https://github.com/finalion/WordQuery)
- [mdict-query](https://github.com/mmjang/mdict-query)
- [pystardict](https://github.com/lig/pystardict)

## License

GPL v3
