from strainer.xhtmlify import xhtmlify, ValidationError


def test_dont_allow_nesting_ps():
    # Disallow nesting <p> tags since that's what HTML 4 says
    # and it simplifies our other logic for when to insert </p>.
    s = '<p><p></p></p>'
    e_exc = "Unexpected closing tag </p> at line 1, column 11 (char 11)"
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_insert_end_p_before_p():
    s = '<p><p></p>'
    e = '<p></p><p></p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_dont_insert_end_p_before_div():
    s = '<p><div></div>'
    e_exc = "Unclosed tag <p> at line 1, column 1 (char 1)"
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_insert_end_p_before_end_h1():
    s = '<h1><p></h1>'
    e = '<h1><p></p></h1>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_li_before_end_ul():
    s = '<ul><li></ul>'
    e = '<ul><li></li></ul>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_li_before_end_ol():
    s = '<ol><li></ol>'
    e = '<ol><li></li></ol>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_td_before_end_tr():
    s = '<tr><td></tr>'
    e = '<tr><td></td></tr>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_th_before_end_tr():
    s = '<tr><th></tr>'
    e = '<tr><th></th></tr>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

