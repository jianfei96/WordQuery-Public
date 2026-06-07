# -*- coding:utf-8 -*-
#
# Copyright (c) 2016-2017 Liang Feng <finalion@gmail.com>
# Copyright (c) 2026 WordQuery Contributors
#
# Support: Report an issue at https://github.com/jianfei96/WordQuery/issues
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version; http://www.gnu.org/copyleft/gpl.html.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import inspect
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import zlib
from collections import defaultdict
from functools import wraps

from http.cookiejar import CookieJar
from aqt import mw
from aqt.qt import QFileDialog
from aqt.utils import showInfo, showText
from ..context import config
from ..lang import _
from ..libs import MdxBuilder, StardictBuilder
from ..utils import MapDict, wrap_css
import requests


def register(label):
    def _deco(cls):
        cls.__register_label__ = label
        return cls
    return _deco


def export(label, index):
    def _with(fld_func):
        @wraps(fld_func)
        def _deco(cls, *args, **kwargs):
            res = fld_func(cls, *args, **kwargs)
            return QueryResult(result=res) if not isinstance(res, QueryResult) else res
        _deco.__export_attrs__ = (label, index)
        return _deco
    return _with


def copy_static_file(filename, new_filename=None, static_dir='static'):
    abspath = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           static_dir, filename)
    shutil.copy(abspath, new_filename if new_filename else filename)


def with_styles(**styles):
    def _with(fld_func):
        @wraps(fld_func)
        def _deco(cls, *args, **kwargs):
            res = fld_func(cls, *args, **kwargs)
            cssfile = styles.get('cssfile', None)
            css = styles.get('css', None)
            jsfile = styles.get('jsfile', None)
            js = styles.get('js', None)
            need_wrap_css = styles.get('need_wrap_css', False)
            class_wrapper = styles.get('wrap_class', '')

            def wrap(html, css_obj, is_file=True):
                if need_wrap_css and class_wrapper:
                    html = u'<div class="{}">{}</div>'.format(class_wrapper, html)
                    return html, wrap_css(css_obj, is_file=is_file, class_wrapper=class_wrapper)[0]
                return html, css_obj

            if cssfile:
                new_cssfile = cssfile if cssfile.startswith('_') else u'_' + cssfile
                copy_static_file(cssfile, new_cssfile)
                res, new_cssfile = wrap(res, new_cssfile)
                res = u'<link type="text/css" rel="stylesheet" href="{0}" />{1}'.format(
                    new_cssfile, res)
            if css:
                res, css = wrap(res, css, is_file=False)
                res = u'<style>{0}</style>{1}'.format(css, res)

            if not isinstance(res, QueryResult):
                return QueryResult(result=res, jsfile=jsfile, js=js)
            else:
                res.set_styles(jsfile=jsfile, js=js)
                return res
        return _deco
    return _with


def find_ffmpeg():
    if config.ffmpeg_path and os.path.isfile(config.ffmpeg_path):
        return config.ffmpeg_path
    common_paths = []
    if platform.system() == 'Darwin':
        common_paths = [
            '/opt/homebrew/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
        ]
    elif platform.system() == 'Linux':
        common_paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
        ]
    elif platform.system() == 'Windows':
        common_paths = [
            os.path.join(os.environ.get('ProgramFiles', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        ]
    for p in common_paths:
        if p and os.path.isfile(p):
            return p
    import shutil as _shutil
    found = _shutil.which('ffmpeg')
    if found:
        return found
    return None


def _extract_tts_sentences(source_text, max_sentences=2):
    text = source_text
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\[sound:[^\]]*\]', '', text)
    chunks = re.split(r'\n+', text)
    sentences = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) > 200:
            parts = re.split(r'(?<=[.!?])\s+', chunk)
            for p in parts:
                p = p.strip()
                if p:
                    sentences.append(p)
        else:
            sentences.append(chunk)
        if len(sentences) >= max_sentences:
            break
    if not sentences:
        return ''
    result = '. '.join(s.rstrip('.!?') for s in sentences)
    if result and result[-1] not in '.!?':
        result += '.'
    return result


class Service(object):

    def __init__(self):
        self._exporters = self.get_exporters()
        self._fields, self._actions = zip(*self._exporters) \
            if self._exporters else (None, None)
        self.query_interval = 0.5

    @property
    def fields(self):
        return self._fields

    @property
    def actions(self):
        return self._actions

    @property
    def exporters(self):
        return self._exporters

    def get_exporters(self):
        flds = dict()
        methods = inspect.getmembers(self, predicate=inspect.ismethod)
        for method in methods:
            export_attrs = getattr(method[1], '__export_attrs__', None)
            if export_attrs:
                label, index = export_attrs
                flds.update({int(index): (label, method[1])})
        sorted_flds = sorted(flds)
        return [flds[key] for key in sorted_flds]

    def active(self, action_label, word, note_fields=None):
        self.word = word
        self.note_fields = note_fields or {}
        if isinstance(self, LocalService):
            self.notify(MapDict(type='text', index=self.work_id,
                                text=u'Building %s...' % self._filename))
            if isinstance(self, MdxService) or isinstance(self, StardictService):
                self.builder.check_build()

        for each in self.exporters:
            if action_label == each[0]:
                self.notify(MapDict(type='info', index=self.work_id,
                                    service_name=self.title,
                                    field_name=action_label,
                                    flag=u'->'))
                result = each[1]()
                self.notify(MapDict(type='info', index=self.work_id,
                                    service_name=self.title,
                                    field_name=action_label,
                                    flag=u'√'))
                return result
        return QueryResult.default()

    def set_notifier(self, progress_update, index):
        self.notify_signal = progress_update
        self.work_id = index

    def notify(self, data):
        self.notify_signal.emit(data)

    @staticmethod
    def get_anki_label(filename, type_):
        formats = {'audio': u'[sound:{0}]',
                   'img': u'<img src="{0}">',
                   'video': u'<video controls="controls" width="100%" height="auto" src="{0}"></video>'}
        return formats[type_].format(filename)

    @export(u"tts", 8)
    def fld_tts(self):
        source_field = config.tts_source_field or ''
        source_text = self.note_fields.get(source_field, '') if (source_field and self.note_fields) else ''
        if not source_text:
            return ''
        tts_text = _extract_tts_sentences(source_text, 2)
        if not tts_text:
            return ''
        media_dir = mw.col.media.dir()
        safe_word = re.sub(r'[^\w]', '_', self.word.lower())[:50]
        mp3_name = 'tts_{}.mp3'.format(safe_word)
        dst = os.path.join(media_dir, u'_' + mp3_name)
        if not os.path.exists(dst):
            self._generate_tts(tts_text, dst)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            return u'[sound:_{}]'.format(mp3_name)
        return ''

    def _generate_tts(self, text, output_path):
        if self._tts_edge(text, output_path):
            return True
        return self._tts_say(text, output_path)

    def _tts_say(self, text, output_path):
        if platform.system() != 'Darwin':
            return False
        voice = config.tts_voice or 'Samantha'
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                              delete=False, encoding='utf-8') as f:
                f.write(text)
                txt_path = f.name
            with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as f:
                aiff_path = f.name
            subprocess.run(
                ['say', '-v', voice, '-o', aiff_path, '-f', txt_path],
                capture_output=True, timeout=10
            )
            if not os.path.exists(aiff_path) or os.path.getsize(aiff_path) == 0:
                return False
            ffmpeg = find_ffmpeg()
            if ffmpeg:
                subprocess.run(
                    [ffmpeg, '-y', '-i', aiff_path,
                     '-acodec', 'libmp3lame', '-q:a', '2', output_path],
                    capture_output=True, timeout=10
                )
            else:
                shutil.move(aiff_path, output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception:
            return False
        finally:
            for p in (txt_path, aiff_path):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except Exception:
                    pass

    def _tts_edge(self, text, output_path):
        voice = config.tts_voice or 'en-US-AriaNeural'
        if ' ' in voice or '-' not in voice:
            voice = 'en-US-AriaNeural'
        try:
            subprocess.run(
                ['edge-tts', '--voice', voice, '--text', text,
                 '--write-media', output_path],
                capture_output=True, timeout=15
            )
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except FileNotFoundError:
            return False
        except Exception:
            return False


class WebService(Service):

    def __init__(self):
        super(WebService, self).__init__()
        self.cache = defaultdict(defaultdict)
        self._cookie = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie))
        self.query_interval = 1

    def cache_this(self, result):
        self.cache[self.word].update(result)
        return result

    def cached(self, key):
        return (self.word in self.cache) and (key in self.cache[self.word])

    def cache_result(self, key):
        return self.cache[self.word].get(key, u'')

    @property
    def title(self):
        return self.__register_label__

    @property
    def unique(self):
        return self.__class__.__name__

    def get_response(self, url, data=None, headers=None, timeout=10):
        default_headers = {'User-Agent': 'Anki WordQuery',
                           'Accept-Encoding': 'gzip'}
        if headers:
            default_headers.update(headers)
        request = urllib.request.Request(url, headers=default_headers)
        try:
            response = self._opener.open(request, data=data, timeout=timeout)
            resp_data = response.read()
            if response.info().get('Content-Encoding') == 'gzip':
                resp_data = zlib.decompress(resp_data, 16 + zlib.MAX_WBITS)
            return resp_data.decode('utf-8')
        except Exception:
            return ''

    @classmethod
    def download(cls, url, filename):
        try:
            return urllib.request.urlretrieve(url, filename)
        except Exception:
            try:
                with open(filename, "wb") as f:
                    f.write(requests.get(url).content)
                return True
            except Exception:
                pass


class LocalService(Service):

    def __init__(self, dict_path):
        super(LocalService, self).__init__()
        self.dict_path = dict_path
        self.builder = None
        self.missed_css = set()

    @property
    def unique(self):
        return self.dict_path

    @property
    def title(self):
        return self.__register_label__

    @property
    def _filename(self):
        return os.path.splitext(os.path.basename(self.dict_path))[0]


class MdxService(LocalService):

    _mdd_key_cache = {}
    _mdd_key_cache_path = None

    def __init__(self, dict_path):
        super(MdxService, self).__init__(dict_path)
        self.media_cache = defaultdict(set)
        self.cache = defaultdict(str)
        self.raw_html_cache = {}
        self.query_interval = 0.01
        self.styles = []
        self.builder = MdxBuilder(dict_path)
        self.builder.get_header()

    @staticmethod
    def support(dict_path):
        return os.path.isfile(dict_path) and dict_path.lower().endswith('.mdx')

    @property
    def title(self):
        if config.use_filename or not self.builder._title or self.builder._title.startswith('Title'):
            return self._filename
        else:
            return self.builder.meta['title']

    @export(u"default", 0)
    def fld_whole(self):
        html = self.get_html()
        js = re.findall(r'<script.*?>.*?</script>', html, re.DOTALL)
        return QueryResult(result=html, js=u'\n'.join(js))

    def _get_parser(self):
        if not hasattr(self, '_parser_instance'):
            self._parser_instance = None
            title = self.title.lower() if self.title else ''
            for parser_cls in _PARSERS:
                if parser_cls.match(title, self._filename):
                    self._parser_instance = parser_cls()
                    break
        return self._parser_instance

    @export(u"headword", 1)
    def fld_headword(self):
        parser = self._get_parser()
        if parser:
            return parser.fld_headword(self._get_raw_html())
        return ''

    @export(u"phonetic", 2)
    def fld_phonetic(self):
        parser = self._get_parser()
        if parser:
            return parser.fld_phonetic(self._get_raw_html())
        return ''

    @export(u"pos", 3)
    def fld_pos(self):
        parser = self._get_parser()
        if parser:
            return parser.fld_pos(self._get_raw_html())
        return ''

    @export(u"pos_cn", 4)
    def fld_pos_cn(self):
        parser = self._get_parser()
        if parser:
            return parser.fld_pos_cn(self._get_raw_html())
        return ''

    @export(u"definition", 5)
    def fld_definition(self):
        parser = self._get_parser()
        if parser:
            return parser.fld_definition(self._get_raw_html())
        return ''

    @export(u"example", 6)
    def fld_example(self):
        parser = self._get_parser()
        if parser:
            return parser.fld_example(self._get_raw_html())
        return ''

    @export(u"audio", 7)
    def fld_audio(self):
        raw = self._get_raw_html()
        sounds = re.findall(r'href="sound:(.*?\.(?:mp3|wav|spx|ogg))"', raw)
        if not sounds:
            return ''
        media_dir = mw.col.media.dir()
        first_sound = sounds[0]
        src_filename = first_sound.split('/')[-1] if '/' in first_sound else first_sound
        ext = os.path.splitext(src_filename)[1].lower()
        if ext in ('.spx', '.ogg'):
            mp3_name = os.path.splitext(src_filename)[0] + '.mp3'
            dst = os.path.join(media_dir, u'_' + mp3_name)
            if not os.path.exists(dst):
                src_dst = os.path.join(media_dir, u'_' + src_filename)
                if not os.path.exists(src_dst):
                    self._extract_mdd_file(first_sound, src_dst)
                if os.path.exists(src_dst):
                    self._convert_audio(src_dst, dst)
            return u'[sound:_{}]'.format(mp3_name)
        else:
            dst = os.path.join(media_dir, u'_' + src_filename)
            if not os.path.exists(dst):
                self._extract_mdd_file(first_sound, dst)
            return u'[sound:_{}]'.format(src_filename)

    def _convert_audio(self, src_path, dst_path):
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return
        try:
            subprocess.run(
                [ffmpeg, '-y', '-i', src_path,
                 '-acodec', 'libmp3lame', '-q:a', '2', dst_path],
                capture_output=True, timeout=30
            )
        except Exception:
            pass

    def _build_mdd_key_cache(self, mdd_path):
        if MdxService._mdd_key_cache_path == mdd_path and MdxService._mdd_key_cache:
            return
        try:
            from ..libs.mdict.readmdict import MDD as ReadMDD
            cache = {}
            mdd = ReadMDD(mdd_path)
            for key, value in mdd.items():
                cache[key] = value
            MdxService._mdd_key_cache = cache
            MdxService._mdd_key_cache_path = mdd_path
        except Exception:
            MdxService._mdd_key_cache = {}
            MdxService._mdd_key_cache_path = None

    def _extract_mdd_file(self, mdd_key, dst_path):
        try:
            bytes_list = self.builder.mdd_lookup(mdd_key)
            if bytes_list:
                with open(dst_path, 'wb') as f:
                    f.write(bytes_list[0])
                return True
        except (sqlite3.OperationalError, Exception):
            pass
        try:
            from ..libs.mdict.readmdict import MDD as ReadMDD
            mdd_path = os.path.splitext(self.dict_path)[0] + '.mdd'
            if not os.path.exists(mdd_path):
                return False
            clean_key = mdd_key.lstrip('/')
            bs = chr(92)
            norm_key = bs + clean_key.replace('/', bs)
            norm_key_bytes = norm_key.encode('utf-8')
            self._build_mdd_key_cache(mdd_path)
            value = MdxService._mdd_key_cache.get(norm_key_bytes)
            if value is not None:
                with open(dst_path, 'wb') as f:
                    f.write(value)
                return True
        except Exception:
            pass
        return False

    def get_html(self):
        if not self.cache[self.word]:
            html = ''
            result = self.builder.mdx_lookup(self.word)
            if result:
                if result[0].upper().find(u"@@@LINK=") > -1:
                    self.word = result[0][len(u"@@@LINK="):].strip()
                    return self.get_html()
                else:
                    raw = result[0] if isinstance(result[0], str) else result[0].decode('utf-8', errors='ignore')
                    self.raw_html_cache[self.word] = raw
                    html = self.adapt_to_anki(raw)
                    self.cache[self.word] = html
        return self.cache[self.word]

    def _get_raw_html(self):
        if self.word not in self.raw_html_cache:
            self.get_html()
        return self.raw_html_cache.get(self.word, '')

    def adapt_to_anki(self, html):
        media_dir = mw.col.media.dir()
        media_files_set = set()
        mcss = re.findall(r'href="(\S+?\.css)"', html)
        media_files_set.update(set(mcss))
        mjs = re.findall(r'src="([\w\./]\S+?\.js)"', html)
        media_files_set.update(set(mjs))
        msrc = re.findall(r'<img.*?src="([\w\./]\S+?)".*?>', html)
        media_files_set.update(set(msrc))
        msound = re.findall(r'href="sound:(.*?\.(?:mp3|wav|spx|ogg))"', html)
        if config.export_media:
            media_files_set.update(set(msound))
        for each in media_files_set:
            html = html.replace(each, u'_' + each.split('/')[-1])
        p = re.compile(
            r'<a[^>]+?href=\"(sound:_.*?\.(?:mp3|wav|spx|ogg))\"[^>]*?>(.*?)</a>')
        html = p.sub(u"[\\1]\\2", html)
        self.save_media_files(media_files_set)
        for cssfile in mcss:
            cssfile = '_' + os.path.basename(cssfile.replace('\\', os.path.sep))
            css_abs = os.path.join(media_dir, cssfile)
            if not os.path.exists(css_abs):
                dict_dir = os.path.dirname(self.dict_path)
                src = os.path.join(dict_dir, os.path.basename(cssfile))
                if os.path.isfile(src):
                    try:
                        shutil.copy(src, css_abs)
                    except Exception:
                        pass
            if not os.path.exists(css_abs):
                self.missed_css.add(cssfile[1:])
            new_css_file, wrap_class_name = wrap_css(cssfile)
            html = html.replace(cssfile, new_css_file)
            html = u'<div class="{0}">{1}</div>'.format(wrap_class_name, html)
        return html

    def save_file(self, filepath_in_mdx, savepath=None):
        basename = os.path.basename(filepath_in_mdx.replace('\\', os.path.sep))
        if savepath is None:
            savepath = os.path.join(mw.col.media.dir(), '_' + basename)
        if os.path.exists(savepath):
            return savepath
        try:
            bytes_list = self.builder.mdd_lookup(filepath_in_mdx)
            if bytes_list:
                with open(savepath, 'wb') as f:
                    f.write(bytes_list[0])
                    return savepath
        except (sqlite3.OperationalError, Exception):
            pass
        self._extract_mdd_file(filepath_in_mdx, savepath)
        if os.path.exists(savepath):
            return savepath
        dict_dir = os.path.dirname(self.dict_path)
        src = os.path.join(dict_dir, basename)
        if os.path.isfile(src):
            try:
                shutil.copy(src, savepath)
                return savepath
            except Exception:
                pass
        return None

    def save_media_files(self, data):
        diff = data.difference(self.media_cache['files'])
        self.media_cache['files'].update(diff)
        lst, errors = list(), list()
        wild = [
            '*' + os.path.basename(each.replace('\\', os.path.sep)) for each in diff]
        try:
            for each in wild:
                keys = self.builder.get_mdd_keys(each)
                if not keys:
                    errors.append(each)
                lst.extend(keys)
            for each in lst:
                self.save_file(each)
        except AttributeError:
            pass
        dict_dir = os.path.dirname(self.dict_path)
        try:
            anki_media_dir = mw.col.media.dir()
        except Exception:
            anki_media_dir = os.getcwd()
        for each in list(errors):
            basename = os.path.basename(each.replace('\\', os.path.sep))
            src = os.path.join(dict_dir, basename)
            dst = os.path.join(anki_media_dir, '_' + basename)
            if os.path.isfile(src) and not os.path.exists(dst):
                try:
                    shutil.copy(src, dst)
                    errors.remove(each)
                except Exception:
                    pass
        return errors


class StardictService(LocalService):

    def __init__(self, dict_path):
        super(StardictService, self).__init__(dict_path)
        self.query_interval = 0.05
        self.builder = StardictBuilder(self.dict_path, in_memory=False)
        self.builder.get_header()

    @staticmethod
    def support(dict_path):
        return os.path.isfile(dict_path) and dict_path.lower().endswith('.ifo')

    @property
    def title(self):
        if config.use_filename or not self.builder.ifo.bookname:
            return self._filename
        else:
            return self.builder.ifo.bookname.decode('utf-8')

    @export(u"default", 0)
    def fld_whole(self):
        self.builder.check_build()
        try:
            result = self.builder[self.word]
            result = result.strip().replace('\r\n', '<br />') \
                .replace('\r', '<br />').replace('\n', '<br />')
            return QueryResult(result=result)
        except KeyError:
            return QueryResult.default()


class QueryResult(MapDict):

    def __init__(self, *args, **kwargs):
        super(QueryResult, self).__init__(*args, **kwargs)
        if self['result'] is None:
            self['result'] = ""

    def set_styles(self, **kwargs):
        for key, value in kwargs.items():
            self[key] = value

    @classmethod
    def default(cls):
        return QueryResult(result="")


from .parsers.base import DictParser  # noqa: F401 (re-exported for backward compat)

_PARSERS = []


def _load_parsers():
    parser_dir = os.path.join(os.path.dirname(__file__), 'parsers')
    if not os.path.isdir(parser_dir):
        return
    import importlib as _il
    for fname in os.listdir(parser_dir):
        if fname.endswith('.py') and not fname.startswith('_'):
            try:
                mod = _il.import_module('.parsers.%s' % fname[:-3], __package__)
                for name, cls in inspect.getmembers(mod, predicate=inspect.isclass):
                    if issubclass(cls, DictParser) and cls is not DictParser:
                        _PARSERS.append(cls)
            except Exception:
                pass


_load_parsers()
