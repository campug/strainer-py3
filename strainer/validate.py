"""Provides JSON validation using the best available JSON parser and
   XHTML 1.0 validation if lxml is importable."""

import os
import re
import urlparse

lxml = None  # imported dynamically on first use

try:
    import demjson as json  # most accurate JSON validator AFAIK
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        import json

from pkg_resources import resource_string
from strainer.doctypes import *


__all__ = ['validate_xhtml', 'validate_xhtml_fragment', 'XHTMLSyntaxError',
           'validate_json', 'JSONSyntaxError']


DEFAULT_XHTML_TEMPLATE = ('<html><head><title/></head><body><div>\n'
                          '%s</div></body></html>')


class XHTMLSyntaxError(ValueError):
    pass


class JSONSyntaxError(ValueError):
    pass

_parser = None


def _get_parser():
    global _parser, lxml
    if _parser is not None:
        return _parser
    if lxml is None:
        import lxml.etree

    class CustomResolver(lxml.etree.Resolver):
        def __init__(self):
            super(CustomResolver, self).__init__()
            self.cache = {}
            for filename in ['xhtml1-strict.dtd', 'xhtml1-transitional.dtd',
                             'xhtml-lat1.ent', 'xhtml-special.ent',
                             'xhtml-symbol.ent']:
                url = 'http://www.w3.org/TR/xhtml1/DTD/' + filename
                self.cache[url] = resource_string(__name__, 'dtds/' + filename)

        def resolve(self, url, id, context):
            return self.resolve_string(self.cache[url], context)

    resolver = CustomResolver()
    _parser = lxml.etree.XMLParser(dtd_validation=True, no_network=True)
    _parser.resolvers.add(resolver)
    return _parser


def validate_xhtml(xhtml, doctype=''):
    """Validates that doctype + xhtml matches the DTD.
       If not given or '', doctype will be extracted from the document.
       The resulting doctype must be one of DOCTYPE_XHTML1_STRICT,
       DOCTYPE_XHTML1_TRANSITIONAL or DOCTYPE_XHTML1_FRAMESET.

       Requires lxml."""
    global parser, lxml
    if lxml is None:
        import lxml.etree
    try:
        lxml.etree.fromstring(doctype + xhtml, parser=_get_parser())
    except lxml.etree.XMLSyntaxError, e:
        # Try to fix up the error message so line numbers are
        # relative to xhtml.
        tline = doctype.count('\n')
        message = re.sub(r'line (\d+)',
                         lambda m: 'line %s' % (int(m.group(1)) - tline),
                         e.message)
        raise XHTMLSyntaxError(message)


def validate_xhtml_fragment(xhtml_fragment, doctype=None, template=None):
    """Validates that xhtml_fragment matches the doctype, after it
       has been inserted into a basic template document's body tag.
       If given, doctype should be one of DOCTYPE_XHTML1_STRICT,
       DOCTYPE_XHTML1_TRANSITIONAL or DOCTYPE_XHTML1_FRAMESET.
       The defaults for doctype and template are DOCTYPE_XHTML1_STRICT
       and DEFAULT_XHTML_TEMPLATE respectively.

       Requires lxml."""
    global lxml
    if lxml is None:
        import lxml.etree
    if not doctype:
        doctype = DOCTYPE_XHTML1_STRICT
    if not template:
        template = DEFAULT_XHTML_TEMPLATE
    m = re.compile('.*?(?<!%)%s', re.DOTALL).search(template)
    tline = m.group(0).count('\n') + 1  # line number of %s in template
    xhtml = doctype + (template % xhtml_fragment)
    try:
        lxml.etree.fromstring(xhtml, parser=_get_parser())
    except lxml.etree.XMLSyntaxError, e:
        # Try to fix up the error message so line numbers are
        # relative to the fragment.
        message = re.sub(r'line (\d+)',
                         lambda m: 'line %s' % (int(m.group(1)) - tline),
                         e.message)
        raise XHTMLSyntaxError(message)


def validate_json(jsonstr):
    """Validates that json is a valid JSON string (by loading it)."""
    try:
        json.loads(jsonstr)
    except ValueError, e:
        raise JSONSyntaxError(str(e))
