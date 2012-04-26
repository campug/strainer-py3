from strainer.validate import *
from strainer.doctypes import DOCTYPE_XHTML1_STRICT


def test_validate_xhtml():
    validate_xhtml(DOCTYPE_XHTML1_STRICT +
        '<html><head><title/></head><body/></html>')

def test_validate_xhtml_fragment():
    validate_xhtml_fragment('<a/>')

def test_validate_invalid_xhtml():
    try:
        validate_xhtml('<html/>', doctype=DOCTYPE_XHTML1_STRICT)
    except XHTMLSyntaxError as e:
        assert 'line 1, column 8' in e.message, e.message
        assert 'Element html content does not follow the DTD' in e.message
        assert 'expecting (head, body)' in e.message.replace(' ,', ',')

def test_validate_invalid_xhtml_fragment():
    try:
        validate_xhtml_fragment('</p>')
    except XHTMLSyntaxError as e:
        assert e.message==('Opening and ending tag mismatch: '
                           'div line 0 and p, line 1, column 5'), e.message
