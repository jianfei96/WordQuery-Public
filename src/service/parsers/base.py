import re


class DictParser:
    """Base class for MDX dictionary field parsers.

    Subclass this to add support for a specific MDX dictionary format.
    Each parser provides field extraction methods that parse raw HTML
    from the dictionary entry.

    To add a new parser:
      1. Create a .py file in the parsers/ directory
      2. Subclass DictParser
      3. Implement match() and the field methods you need
      4. The parser is auto-discovered at runtime
    """

    @staticmethod
    def match(title, filename):
        """Return True if this parser handles the given dictionary.

        Args:
            title: the dictionary title from MDX header
            filename: the dictionary filename without extension
        """
        return False

    def fld_headword(self, raw_html):
        return ''

    def fld_phonetic(self, raw_html):
        return ''

    def fld_pos(self, raw_html):
        return ''

    def fld_pos_cn(self, raw_html):
        return ''

    def fld_definition(self, raw_html):
        return ''

    def fld_example(self, raw_html):
        return ''
