"""Performs basic XHTML wellformedness checks."""
import xml.sax
import xml.sax.handler
import htmlentitydefs

from xml.sax._exceptions import SAXException


__all__ = ['is_wellformed_xml', 'is_wellformed_xhtml']

DOCTYPE_XHTML1_STRICT = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
    '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">')


def is_wellformed_xhtml(docpart):
    """Calls is_wellformed_xml with doctype=DOCTYPE_XHTML1_STRICT
       and entitydefs=htmlentitydefs.entitydefs."""
    return is_wellformed_xml(docpart, doctype=DOCTYPE_XHTML1_STRICT,
                             entitydefs=htmlentitydefs.entitydefs)

def is_wellformed_xml(docpart, doctype='', entitydefs={}):
    """Prefixes doctype to docpart and parses the resulting string.
       Returns True if it parses as XML without error. If entitydefs
       is given, checks that all named entity references are keys
       in entitydefs. Does not check against the external DTD declared
       in the doctype.
    """
    doc = doctype + docpart
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    if entitydefs:
        class Handler(xml.sax.handler.ContentHandler):
            def skippedEntity(self, name):
                if name not in entitydefs:
                    raise SAXException(name, None) # we catch this
        h = Handler()
        parser.setContentHandler(h)
    try:
        parser.feed(doc)
        parser.close()
        return True
    except SAXException:  # catches our exception and other parse errors
        return False

def test():
    assert is_wellformed_xhtml('<foo>&nbsp;&auml;&#65;</foo>')

if __name__=='__main__':
    test()
