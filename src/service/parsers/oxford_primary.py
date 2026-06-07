import re
from .base import DictParser


class OxfordPrimaryParser(DictParser):
    """Parser for oxfordPrimary bilingual MDX dictionary."""

    @staticmethod
    def match(title, filename):
        t = title.lower() if title else ''
        f = filename.lower() if filename else ''
        return 'oxfordprimary' in t or 'oxfordprimary' in f

    def fld_headword(self, raw_html):
        m = re.search(r'color="#2894ff"[^>]*><b>([^<]+)</b>', raw_html)
        return m.group(1) if m else ''

    def fld_phonetic(self, raw_html):
        m = re.search(r'size="5">\s*/([^/]+)/', raw_html)
        return '/' + m.group(1) + '/' if m else ''

    def fld_pos(self, raw_html):
        m = re.search(
            r'<b>(interjection|verb|adjective|adverb|noun|pronoun|'
            r'preposition|conjunction|phrasal verb|'
            r'transitive verb|intransitive verb)</b>', raw_html)
        return m.group(1) if m else ''

    def fld_pos_cn(self, raw_html):
        m = re.search(
            r'<b>[^<]+</b>[^<]*</font><font[^>]*>\s*</font><font[^>]*>\s*'
            r'(动词|形容词|副词|名词|代词|介词|连词|感叹词|及物动词|不及物动词|短语动词)',
            raw_html)
        return m.group(1) if m else ''

    def fld_definition(self, raw_html):
        defs = re.findall(r'<font face="Ariel"[^>]*>([^<]+)</font>', raw_html)
        if defs:
            return u'<br>'.join(defs)
        return ''

    def fld_example(self, raw_html):
        examples = re.findall(
            r'<i>([^<]+)</i>.*?<font[^>]*>([^<]+)</font>', raw_html, re.DOTALL)
        if examples:
            return u'<br>'.join(
                u'{}<br>{}'.format(en, zh) for en, zh in examples)
        en_only = re.findall(r'<i>([^<]+)</i>', raw_html)
        return u'<br>'.join(en_only) if en_only else ''
