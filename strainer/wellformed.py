"""Performs basic XHTML wellformedness checks."""
import xml.sax
import xml.sax.handler
import htmlentitydefs

from xml.sax._exceptions import SAXParseException


__all__ = ['is_wellformed_xml', 'is_wellformed_xhtml']

DOCTYPE_XHTML1_STRICT = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
    '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')


def is_wellformed_xhtml(docpart, record_error=None):
    """Calls is_wellformed_xml with doctype=DOCTYPE_XHTML1_STRICT
       and entitydefs=htmlentitydefs.entitydefs."""
    return is_wellformed_xml(docpart, doctype=DOCTYPE_XHTML1_STRICT,
                             entitydefs=htmlentitydefs.entitydefs,
                             record_error=record_error)

def is_wellformed_xml(docpart, doctype='', entitydefs={}, record_error=None):
    """Prefixes doctype to docpart and parses the resulting string.
       Returns True if it parses as XML without error. If entitydefs
       is given, checks that all named entity references are keys
       in entitydefs. Does not check against the external DTD declared
       in the doctype.

       If record_error is not None, it is called with the text of the
       first error message found if there is one (that is, if this function
       will return False).
    """
    doc = doctype + docpart
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    if entitydefs:
        class Handler(xml.sax.handler.ContentHandler):
            def skippedEntity(self, name):
                if name not in entitydefs:
                    raise SAXParseException('Unknown entity reference', None, parser)
        h = Handler()
        parser.setContentHandler(h)
    try:
        parser.feed(doc)
        parser.close()
        return True
    except SAXParseException, e:  # catches our exception and other parse errors
        if record_error is not None:
            line, column = e.getLineNumber(), e.getColumnNumber()
            # Correct location to account for our adding a doctype prefix.
            line -= doctype.count('\n')
            if line == 1:
                column -= len(doctype) - (doctype.rfind('\n') + 1)
            # Convert column to 1-based indexing
            record_error('line %d, column %d: %s' % (line, column+1, e.message))
        return False

def test():
    assert is_wellformed_xhtml('<foo>&nbsp;&auml;&#65;</foo>')

if __name__=='__main__':
    test()
