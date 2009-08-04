from strainer.operators import normalize_to_xhtml


def test_normalize_to_xhtml():
    s = """<form action="" method="post" class="required tableform">
        <div></div>
        </form>"""
    e = """<form action="" class="required tableform" method="post"><div /></form>"""
    r =normalize_to_xhtml(s)
    assert r == e, r

def test_normalize_to_xhtml_with_escapes():
    s = """<form action="" method="post" class="required tableform">
        <div></div>&nbsp;
        </form>"""
    e = """<form action="" class="required tableform" method="post"><div /></form>"""
    r =normalize_to_xhtml(s)
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
    r =normalize_to_xhtml(s)
