#-*- coding:utf-8 -*-
import re
import os
from aqt.utils import showInfo

__all__ = ['add_metaclass', 'wrap_css']


def add_metaclass(metaclass):
    """Class decorator for creating a class with a metaclass."""
    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        slots = orig_vars.get('__slots__')
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        orig_vars.pop('__dict__', None)
        orig_vars.pop('__weakref__', None)
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper


def _get_media_dir():
    try:
        from aqt import mw
        return mw.col.media.dir()
    except Exception:
        return os.getcwd()


def wrap_css(orig_css, is_file=True, class_wrapper=None, new_cssfile_suffix=u'wrap'):

    def process(content):
        # clean the comments
        regx = re.compile(r'/\*.*?\*/', re.DOTALL)
        content = regx.sub(r'', content).strip()
        # add wrappers to all the selectors except the first one
        regx = re.compile(r'([^\r\n,{}]+)(,(?=[^}]*{)|\s*{)', re.DOTALL)
        new_css = regx.sub(u'.{} \\1\\2'.format(class_wrapper), content)
        return new_css

    if is_file:
        if not class_wrapper:
            class_wrapper = os.path.splitext(os.path.basename(orig_css))[0]
        # resolve paths relative to anki media dir
        media_dir = _get_media_dir()
        if not os.path.isabs(orig_css):
            orig_css = os.path.join(media_dir, orig_css)
        basename = os.path.basename(orig_css)
        new_cssfile = os.path.join(media_dir,
            u'{css_name}_{suffix}.css'.format(
                css_name=basename[:basename.rindex('.css')],
                suffix=new_cssfile_suffix))
        # if new css file exists, not process
        # if input original css file doesn't exist, return the new css filename and class wrapper
        # to make the subsequent process easy.
        if os.path.exists(new_cssfile) or not os.path.exists(orig_css):
            return os.path.basename(new_cssfile), class_wrapper
        result = ''
        with open(orig_css, 'rb') as f:
            try:
                result = process(f.read().strip().decode('utf-8', 'ignore'))
            except:
                showInfo('error: ' + orig_css)

        if result:
            with open(new_cssfile, 'wb') as f:
                f.write(result.encode('utf-8'))
        return os.path.basename(new_cssfile), class_wrapper
    else:
        # class_wrapper must be valid.
        assert class_wrapper
        return process(orig_css), class_wrapper
