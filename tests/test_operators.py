import strainer.operators as ops
from nose.tools import raises


def test_normalize_to_xhtml():
    s = """<form action="" method="post" class="required tableform">
        <div></div>
        </form>"""
    e = """<form action="" class="required tableform" method="post"><div /></form>"""
    r = ops.normalize_to_xhtml(s)
    assert r == e, r

def test_normalize_to_xhtml_with_escapes():
    s = """<form action="" method="post" class="required tableform">
        <div></div>&nbsp;
        </form>"""
    e = """<form action="" class="required tableform" method="post"><div /></form>"""
    r = ops.normalize_to_xhtml(s)
    assert r == e, r

def test_fix_xml_with_namespace():
    s = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <body>
    <form action="" method="post" class="required tableform">
        <div></div>&nbsp;
        </form>
    </body>
    </html>"""
    e = """<html><body><form action="" class="required tableform" method="post"><div /></form></body></html>"""
    r = ops.normalize_to_xhtml(s)
    assert r == e, r

def test_eq_xhtml():
    b = "<foo><bar>Value</bar></foo>"
    c = """
<foo>
    <bar>
        Value
    </bar>
</foo>
"""
    ops.eq_xhtml(b, c)

def test_eq_html_wrapped():
    b = "<foo></foo><bar>Value</bar>"
    c = """
<foo>
</foo>
    <bar>
        Value
    </bar>
"""
    ops.eq_xhtml(b, c, True)

@raises(ops.XMLParsingError)
def test_bad_xhtml():
    b = '<foo'
    ops.eq_xhtml(b, b)

@raises(ops.XMLParsingError)
def test_bad_xhtml_too():
    ops.eq_xhtml("<foo/>", '<foo')
