import re

from strainer.xhtmlify import xhtmlify as _xhtmlify, xmlparse, ValidationError


def xhtmlify(html):
    """Call the real xhtmlify and check it outputs well-formed XML
       and that it it idempotent (makes no changes when fed its output)."""
    xhtml = _xhtmlify(html)
    try:
        # ET can't handle <!...>
        stripped_xhtml = re.sub(r'(?s)<!(?!\[).*?>', '', xhtml)
        xmlparse(stripped_xhtml)
    except Exception, e:
        assert False, (stripped_xhtml, str(e))
    assert xhtml == _xhtmlify(xhtml), xhtml
    return xhtml

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

def test_lowercases_attrs():
    s = '<p ID=foo clAss=\'bar\'><input valUe="TesT">'
    e = '<p id="foo" class=\'bar\'><input value="TesT" /></p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_quoted_dquote_attr_is_unchanged():
    s = r'''<img alt='"' /><img alt='&quot;' />'''
    e = r'''<img alt='"' /><img alt='&quot;' />'''
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_quoted_squote_attr_is_unchanged():
    s = r'''<img alt="'" /><img alt='&apos;' />'''
    e = r'''<img alt="'" /><img alt='&apos;' />'''
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_single_dquote_attr():
    s = r'''<img alt=" />'''
    e = r'''<img alt="&quot;" />'''
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_single_squote_attr():
    s = r'''<img alt='>'''
    e = r'''<img alt="'" />'''
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_dquoted_lt_attr_is_replaced():
    s = r'''<img alt="<"/>'''
    e = r'''<img alt="&lt;"/>'''
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_squoted_lt_attr_is_replaced():
    s = r'''<img alt='<'/>'''
    e = r'''<img alt='&lt;'/>'''
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_self_closing():
    s = '<br><input value="test"><input id="x" value="test"  >'
    e = '<br /><input value="test" /><input id="x" value="test"  />'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

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
    e = '<p><div></div></p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

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

def test_ampersand():
    s = '<p>&</p><p>&amp;</p>'
    e = '<p>&amp;</p><p>&amp;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_less_than():
    s = '<'
    e_exc = 'Unescaped "<" or unfinished tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_less_than2():
    s = '<p><</p>'
    e_exc = 'Unescaped "<" or unfinished tag at line 1, column 4 (char 4)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_greater_than():
    s = '>'
    e = '>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_apos():
    s = "<p>'</p><p>&apos;</p>"
    e = "<p>'</p><p>&apos;</p>"
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_quot():
    s = '<p>"</p><p>&quot;</p>'
    e = '<p>"</p><p>&quot;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_euro():
    s = '<p>&euro;</p>'
    e = '<p>&#x20ac;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_unknown_entity():
    s = '<p>&nosuch;</p>'
    e = '<p>&amp;nosuch;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_cdata_end_marker():
    s = ']]>'
    e = ']]&gt;'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_end_tag_in_cdata():
    s = '<p><![CDATA[</p>]]></p>'
    e = '<p><![CDATA[</p>]]></p>'
    # '<p>&lt;/p></p>' would be a better XHTML/HTML polyglot, but
    # would break our rule of only making changes where necessary.
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_unclosed_cdata():
    s = '<p><![CDATA[</p>'
    e_exc = 'Unescaped "<" or unfinished tag at line 1, column 4 (char 4)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

# <script> and <style> tags are a complete nightmare.  Our output has to
# parse sensibly in both HTML and XHTML parsers, which is far from easy.
# Our approach is to only escape '<', '>' and '&', and to do it in different
# ways depending on the JavaScript/CSS syntactic context.  Escaping > is
# needed to prevent validity-breaking occurrences of "]]>".
#
# Possible JavaScript/CSS syntactic contexts we need to handle:
#
#   * a string, e.g. "<" or '&'
#   * a comment, e.g. /* < */  or  // &
#   * single tokens: 1 < 2  or  a &b;  (mustn't confuse this with an entity)
#   * a CSS URL
#   * invalid, e.g. <&]]>
#
# We can simplify this to three cases:
#
#   a) inside a string (with either kind of delimiter),
#   b) inside a block comment, or
#   c) other.
#
# We escape <, > and & in the three cases as:
#   a) \x3c, \x3e and \x26  (also replaces \<, \> and \>)
#   b) <![CDATA[<]]>, <![CDATA[>]]> and <![CDATA[&]]>
#   c) /*<![CDATA[<]]>*/, /*<![CDATA[>]]>*/ and /*<![CDATA[&]]>*/
#
# We must not change any text already inside <![CDATA[...]]>.
def test_script_simple():
    s = '<script>/* test */</script>'
    e = '<script>/* test */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt():
    s = '<script> 1 < 2 </script>'
    e = '<script> 1 /*<![CDATA[*/ < /*]]>*/ 2 </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt():
    s = '<script> 1 > 2 </script>'
    e = '<script> 1 /*<![CDATA[*/ > /*]]>*/ 2 </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp():
    s = '<script> 1 & 2 </script>'
    e = '<script> 1 /*<![CDATA[*/ & /*]]>*/ 2 </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_entity():
    s = '<script>var amp=2; amp += 3 &amp;</script>'
    e = '<script>var amp=2; amp += 3 /*<![CDATA[*/ & /*]]>*/amp;</script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_block_comment():
    s = '<script>/* < */</script>'
    e = '<script>/* <![CDATA[<]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_block_comment():
    s = '<script>/* > */</script>'
    e = '<script>/* <![CDATA[>]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_block_comment():
    s = '<script>/* & */</script>'
    e = '<script>/* <![CDATA[&]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_line_comment():
    s = '<script>// < </script>'
    e = '<script>// /*<![CDATA[*/ < /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_line_comment():
    s = '<script>// > </script>'
    e = '<script>// /*<![CDATA[*/ > /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_line_comment():
    s = '<script>// & </script>'
    e = '<script>// /*<![CDATA[*/ & /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_end_marker_in_block_comment():
    s = '<script>/* <![CDATA[x]]> ]]> */</script>'
    e = '<script>/* <![CDATA[x]]> ]]<![CDATA[>]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_end_marker_in_line_comment():
    s = '<script>// <![CDATA[x]]> ]]> </script>'
    e = '<script>// <![CDATA[x]]> ]]/*<![CDATA[*/ > /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_dquote_string():
    s = r'<script> " \"< " </script>'
    e = r'<script> " \"\x%02x " </script>' % ord('<')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_dquote_string():
    s = r'<script> " \"> " </script>'
    e = r'<script> " \"\x%02x " </script>' % ord('>')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_dquote_string():
    s = r'<script> " \"& " </script>'
    e = r'<script> " \"\x%02x " </script>' % ord('&')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_squote_string():
    s = r"<script> ' \'< ' </script>"
    e = r"<script> ' \'\x%02x ' </script>" % ord('<')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_squote_string():
    s = r"<script> ' \'> ' </script>"
    e = r"<script> ' \'\x%02x ' </script>" % ord('>')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_squote_string():
    s = r"<script> ' \'& ' </script>"
    e = r"<script> ' \'\x%02x ' </script>" % ord('&')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_ends_in_squote_string():
    s = r"<script> <![CDATA['x ]]>& ' </script>"
    e = r"<script> <![CDATA['x ]]>\x%02x ' </script>" % ord('&')
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_end_script_end_cdata_end_script():
    s = r"<script><![CDATA[</script>]]></script>"
    e = r"<script><![CDATA[</script>]]></script>"
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_space_before_tag_name():
    s = r"< p>"
    e_exc = 'Malformed tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_pi_unsupported():
    # If adding support, see http://bugs.python.org/issue2746
    # It would be easy to accidentally introduce an XSS vector.
    s = r"<p><?php 1 & 2 ?></p>"
    e_exc = 'Malformed tag at line 1, column 4 (char 4)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_doctype_is_uppercased():
    s = r'<!doctype html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    e = r'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_bad_character_reference():
    s = r'<p>&#7;</p>'
    e = r'<p>&amp;#7;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_repeated_attribute():
    s = r"<p><div style='margin-top: 0px' id=x style='margin-left: 0px' />"
    e_exc = 'Repeated attribute "style" at line 1, column 4 (char 4)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_attribute_minimization():
    s = r'<option selected>'
    e = r'<option selected="selected"></option>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_junk_in_final_attribute():
    # Including the endslash is correct, we try to treat our input as HTML.
    s = r'<p x=:;"/><img>'
    e = r'<p x=":;&quot;/"><img /></p>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_one_colon_in_name():
    s = r'<py:test xmlns:py="..."/>'
    e = r'<py:test xmlns:py="..."/>'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert False, exc
    else:
        assert r==e, r

def test_two_colons_in_name():
    s = r'<a:b:c/>'
    e_exc = r'Malformed tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError, exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r
