import re
from .base import DictParser


class MW11SoundParser(DictParser):
    """Parser for Merriam-Webster 11th Collegiate (MW11sound) MDX dictionary."""

    @staticmethod
    def match(title, filename):
        t = title.lower() if title else ''
        f = filename.lower() if filename else ''
        return 'mw11sound' in t or 'mw11sound' in f or 'merriam' in f

    def fld_headword(self, raw_html):
        m = re.search(r'font-weight:bold[^>]*>([^<]+)</font>', raw_html)
        if m:
            return m.group(1).replace('\u00b7', '')
        return ''

    def fld_phonetic(self, raw_html):
        m = re.search(r'\\\\([^\\]+)\\\\', raw_html)
        return '/' + m.group(1) + '/' if m else ''

    def fld_pos(self, raw_html):
        m = re.search(r'color=#CA0000>([^<]+)</font>', raw_html)
        return m.group(1) if m else ''

    def fld_definition(self, raw_html):
        m = re.search(r'color=#CA0000>[^<]+</font>(.+)', raw_html, re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
            text = re.sub(r'\s+', ' ', text)
            return text[:200] if text else ''
        return ''
