from strainer.validate import *
from strainer.doctypes import DOCTYPE_XHTML1_STRICT
from strainer.xhtmlify import PY3


def test_validate_xhtml():
    validate_xhtml(DOCTYPE_XHTML1_STRICT +
        '<html><head><title/></head><body/></html>')


def test_validate_xhtml_fragment():
    validate_xhtml_fragment('<a/>')


def test_validate_invalid_xhtml():
    try:
        validate_xhtml('<html/>', doctype=DOCTYPE_XHTML1_STRICT)
    except XHTMLSyntaxError as e:
        emsg = e.args[0] if PY3 else e.message
        assert 'line 1, column 8' in emsg, emsg
        assert 'Element html content does not follow the DTD' in emsg
        assert 'expecting (head, body)' in emsg.replace(' ,', ',')


def test_validate_invalid_xhtml_fragment():
    try:
        validate_xhtml_fragment('</p>')
    except XHTMLSyntaxError as e:
        emsg = e.args[0] if PY3 else e.message
        assert emsg == ('Opening and ending tag mismatch: '
                        'div line 0 and p, line 1, column 5'), emsg
