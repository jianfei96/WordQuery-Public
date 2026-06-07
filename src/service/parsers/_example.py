"""
Example parser template for WordQuery.

To create a parser for your own MDX dictionary:
1. Copy this file and rename it (e.g., mydict.py)
2. Update the match() method to identify your dictionary
3. Implement the field methods you need
4. The parser will be auto-discovered at runtime

The raw_html parameter contains the raw HTML from the MDX entry,
before any Anki adaptation (no media path rewriting).
"""

import re
from .base import DictParser


class ExampleParser(DictParser):
    """Example parser - customize this for your dictionary."""

    @staticmethod
    def match(title, filename):
        # Return True when this parser should be used.
        # 'title' comes from the MDX header, 'filename' is the .mdx filename
        return 'example' in (title or '').lower()

    def fld_headword(self, raw_html):
        # Extract the headword from raw HTML
        # Example: m = re.search(r'<b>(.*?)</b>', raw_html)
        #          return m.group(1) if m else ''
        return ''

    def fld_phonetic(self, raw_html):
        # Extract phonetic transcription
        return ''

    def fld_pos(self, raw_html):
        # Extract part of speech (English)
        return ''

    def fld_pos_cn(self, raw_html):
        # Extract part of speech (Chinese), if applicable
        return ''

    def fld_definition(self, raw_html):
        # Extract definition(s)
        return ''

    def fld_example(self, raw_html):
        # Extract example sentences
        return ''
