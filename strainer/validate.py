"""Provides XHTML 1.0 validation using lxml."""
import lxml.etree  # the stdlib's expat parser can't do validation
import os
import re
import urlparse

from pkg_resources import resource_string


__all__ = [
    'validate_xhtml',
    'validate_xhtml_fragment',
    'XHTMLSyntaxError',
    'DOCTYPE_XHTML1_STRICT',
    'DOCTYPE_XHTML1_TRANSITIONAL',
    'DOCTYPE_XHTML1_FRAMESET',
#    'DEFAULT_XHTML_TEMPLATE',
]

DOCTYPE_XHTML1_STRICT = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
    '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n')
DOCTYPE_XHTML1_TRANSITIONAL = (
   '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
   '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n')
DOCTYPE_XHTML1_FRAMESET = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Frameset//EN" '
    '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd">\n')

DEFAULT_XHTML_TEMPLATE = ('<html><head><title/></head><body>\n'
                          '%s</body></html>')

class XHTMLSyntaxError(RuntimeError):
    pass

_parser = None

def _get_parser():
    global _parser
    if _parser is not None:
        return _parser
    class CustomResolver(lxml.etree.Resolver):
        def __init__(self):
            super(CustomResolver, self).__init__()
            self.cache = {}
            for filename in ['xhtml1-strict.dtd', 'xhtml1-transitional.dtd',
                             'xhtml-lat1.ent', 'xhtml-special.ent',
                             'xhtml-symbol.ent']:
                url = 'http://www.w3.org/TR/xhtml1/DTD/' + filename
                self.cache[url] = resource_string(__name__, 'dtds/'+filename)

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
       DOCTYPE_XHTML1_TRANSITIONAL or DOCTYPE_XHTML1_FRAMESET."""
    try:
        lxml.etree.fromstring(doctype + xhtml, parser=_get_parser())
    except lxml.etree.XMLSyntaxError, e:
        # Try to fix up the error message so line numbers are
        # relative to the fragment.
        tline = doctype.count('\n')
        message = re.sub(r'line (\d+)',
                         lambda m: 'line %s' % (int(m.group(1))-tline),
                         e.message)
        raise XHTMLSyntaxError(message)

def validate_xhtml_fragment(xhtml_fragment, doctype=None, template=None):
    """Validates that xhtml_fragment matches the doctype, after it
       has been inserted into a basic template document's body tag.
       If given, doctype should be one of DOCTYPE_XHTML1_STRICT,
       DOCTYPE_XHTML1_TRANSITIONAL or DOCTYPE_XHTML1_FRAMESET.
       The defaults for doctype and template are DOCTYPE_XHTML1_STRICT
       and DEFAULT_XHTML_TEMPLATE respectively."""
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
                         lambda m: 'line %s' % (int(m.group(1))-tline),
                         e.message)
        raise XHTMLSyntaxError(message)
