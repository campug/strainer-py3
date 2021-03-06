import re
import encodings.aliases
import codecs
import six

from strainer.xhtmlify import xhtmlify as _xhtmlify, xmlparse, ValidationError
from strainer.xhtmlify import sniff_encoding, fix_xmldecl
from strainer.doctypes import DOCTYPE_XHTML1_STRICT


def xhtmlify(html, *args, **kwargs):
    """Call the real xhtmlify and check it outputs well-formed XML
       and that it is idempotent (makes no changes when fed its output)."""
    _wrap = None
    if '_wrap' in kwargs:
        _wrap = kwargs.pop('_wrap')
    unicode_input = isinstance(html, six.text_type)
    xhtml = _xhtmlify(html, *args, **kwargs)
    assert isinstance(xhtml, six.text_type) == unicode_input
    regex_type = six.u if unicode_input else six.b
    stripped_xhtml = None
    try:
        # ET can't handle <!...>
        stripped_xhtml = re.sub(regex_type(r'(?s)<!(?!\[).*?>'), '', xhtml)
        xmlparse(stripped_xhtml, wrap=_wrap)
    except Exception as e:
        assert False, (stripped_xhtml, str(e))
    assert xhtml == _xhtmlify(xhtml, *args, **kwargs), xhtml
    return xhtml

def test_simple1():
    s = '<p><b><i>test'
    e = '<p><b><i>test</i></b></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_simple2():
    s = '<p>'
    e = '<p></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_simple_comment():
    s = '<!-- test -->'
    e = '<!-- test -->'  # TODO: what to do about < and > in comments?
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_whitespace_in_tag():
    s = ('''<meta\thttp-equiv\f\f= 'content-type'\nid=x '''
         '''content =\ntext/html;charset=utf-8>''')
    e = ('''<meta\thttp-equiv  = 'content-type'\nid="x" '''
         '''content =\n"text/html;charset=utf-8" />''')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, repr(r)

def test_touching_attrs():
    s = '''<p id="a"class=b><br id=d/></p>'''
    e = '''<p id="a" class="b"><br id="d/" /></p>'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, repr(r)

def test_bad_attr():
    s = '''<a b='1'c'=2/>'''
    e_exc = "Malformed tag contents at line 1, column 10 (char 10)"
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_bad_attr2():
    s = '''<a\tb="b>c'\t>'''
    e = '''<a\tb="&quot;b">c'\t&gt;</a>'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, repr(r)

def test_mini_p():
    s = '<p/>'
    e = '<p/>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, repr(r)

def test_dont_allow_nesting_ps():
    # Disallow nesting <p> tags since that's what HTML 4 says
    # and it simplifies our other logic for when to insert </p>.
    s = '<p><p></p></p>'
    e_exc = "Unexpected closing tag </p> at line 1, column 11 (char 11)"
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_lowercases_attrs():
    s = '<p ID=foo clAss=\'bar\'><input valUe="TesT">'
    e = '<p id="foo" class=\'bar\'><input value="TesT" /></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_quoted_dquote_attr_is_unchanged():
    s = r'''<img alt='"' /><img alt='&quot;' />'''
    e = r'''<img alt='"' /><img alt='&quot;' />'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_quoted_squote_attr_is_unchanged():
    s = r'''<img alt="'" /><img alt='&apos;' />'''
    e = r'''<img alt="'" /><img alt='&apos;' />'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_single_dquote_attr():
    s = r'''<img alt=" />'''
    e = r'''<img alt="&quot;" />'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_single_squote_attr():
    s = r'''<img alt='>'''
    e = r'''<img alt="'" />'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_dquoted_lt_attr_is_replaced():
    s = r'''<img alt="<"/>'''
    e = r'''<img alt="&lt;"/>'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_squoted_lt_attr_is_replaced():
    s = r'''<img alt='<'/>'''
    e = r'''<img alt='&lt;'/>'''
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_self_closing():
    s = '<br><input value="test"><input id="x" value="test"  >'
    e = '<br /><input value="test" /><input id="x" value="test"  />'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_p_before_p():
    s = '<p><p></p>'
    e = '<p></p><p></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_dont_insert_end_p_before_div():
    s = '<p><div></div>'
    e = '<p><div></div></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_p_before_end_h1():
    s = '<h1><p></h1>'
    e = '<h1><p></p></h1>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_li_before_end_ul():
    s = '<ul><li></ul>'
    e = '<ul><li></li></ul>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_li_before_end_ol():
    s = '<ol><li></ol>'
    e = '<ol><li></li></ol>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_td_before_end_tr():
    s = '<tr><td></tr>'
    e = '<tr><td></td></tr>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_insert_end_th_before_end_tr():
    s = '<tr><th></tr>'
    e = '<tr><th></th></tr>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_ampersand():
    s = '<p title="&">&</p><p>&amp;</p>'
    e = '<p title="&amp;">&amp;</p><p>&amp;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_less_than():
    s = '<'
    e_exc = 'Unescaped "<" or unfinished tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_less_than2():
    s = '<p><</p>'
    e_exc = 'Unescaped "<" or unfinished tag at line 1, column 4 (char 4)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_greater_than():
    s = '>'
    e = '&gt;'  # '>' would strictly be ok too...
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_apos():
    s = "<p>'</p><p>&apos;</p>"
    e = "<p>'</p><p>&apos;</p>"
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_quot():
    s = '<p>"</p><p>&quot;</p>'
    e = '<p>"</p><p>&quot;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_euro():
    s = '<p>&euro;</p>'
    e = '<p>&#x20ac;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_unknown_entity():
    s = '<p>&nosuch;</p>'
    e = '<p>&amp;nosuch;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_cdata_end_marker():
    s = ']]>'
    e = ']]&gt;'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
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
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_unclosed_cdata():
    s = '<p><![CDATA[</p>'
    e_exc = 'Unescaped "<" or unfinished tag at line 1, column 4 (char 4)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
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
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt():
    s = '<script> 1 < 2 </script>'
    e = '<script> 1 /*<![CDATA[*/ < /*]]>*/ 2 </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt():
    s = '<script> 1 > 2 </script>'
    e = '<script> 1 /*<![CDATA[*/ > /*]]>*/ 2 </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp():
    s = '<script> 1 & 2 </script>'
    e = '<script> 1 /*<![CDATA[*/ & /*]]>*/ 2 </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_entity():
    s = '<script>var amp=2; amp += 3 &amp;</script>'
    e = '<script>var amp=2; amp += 3 /*<![CDATA[*/ & /*]]>*/amp;</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_block_comment():
    s = '<script>/* < */</script>'
    e = '<script>/* <![CDATA[<]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_block_comment():
    s = '<script>/* > */</script>'
    e = '<script>/* <![CDATA[>]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_block_comment():
    s = '<script>/* & */</script>'
    e = '<script>/* <![CDATA[&]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_line_comment():
    s = '<script>// < </script>'
    e = '<script>// /*<![CDATA[*/ < /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_line_comment():
    s = '<script>// > </script>'
    e = '<script>// /*<![CDATA[*/ > /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_line_comment():
    s = '<script>// & </script>'
    e = '<script>// /*<![CDATA[*/ & /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_end_marker_in_block_comment():
    s = '<script>/* <![CDATA[x]]> ]]> */</script>'
    e = '<script>/* <![CDATA[x]]> ]]<![CDATA[>]]> */</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_end_marker_in_line_comment():
    s = '<script>// <![CDATA[x]]> ]]> </script>'
    e = '<script>// <![CDATA[x]]> ]]/*<![CDATA[*/ > /*]]>*/ </script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_dquote_string():
    s = r'<script> " \"< " </script>'
    e = r'<script> " \"\x%02x " </script>' % ord('<')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_dquote_string():
    s = r'<script> " \"> " </script>'
    e = r'<script> " \"\x%02x " </script>' % ord('>')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_dquote_string():
    s = r'<script> " \"& " </script>'
    e = r'<script> " \"\x%02x " </script>' % ord('&')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_esc_lt_in_dquote_string():
    s = r'<script> " \< " </script>'
    e = r'<script> " \x%02x " </script>' % ord('<')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_esc_gt_in_dquote_string():
    s = r'<script> " \> " </script>'
    e = r'<script> " \x%02x " </script>' % ord('>')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_lt_in_squote_string():
    s = r"<script> ' \'< ' </script>"
    e = r"<script> ' \'\x%02x ' </script>" % ord('<')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_gt_in_squote_string():
    s = r"<script> ' \'> ' </script>"
    e = r"<script> ' \'\x%02x ' </script>" % ord('>')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_amp_in_squote_string():
    s = r"<script> ' \'& ' </script>"
    e = r"<script> ' \'\x%02x ' </script>" % ord('&')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_ends_in_squote_string():
    s = r"<script> <![CDATA['x ]]>& ' </script>"
    e = r"<script> <![CDATA['x ]]>\x%02x ' </script>" % ord('&')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_esc_lt_in_squote_string():
    s = r"<script> ' \< ' </script>"
    e = r"<script> ' \x%02x ' </script>" % ord('<')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_esc_gt_in_squote_string():
    s = r"<script> ' \> ' </script>"
    e = r"<script> ' \x%02x ' </script>" % ord('>')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_end_script_end_cdata_end_script():
    s = r"<script><![CDATA[</script>]]></script>"
    e = r"<script><![CDATA[</script>]]></script>"
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_unexpected_cdata_end_in_dquote_string():
    s = r'<script>"<]]>"</script>'
    e = r'<script>"\x%02x]]\x%02x"</script>' % (ord('<'), ord('>'))
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_unexpected_tag_gets_escaped():
    s = r'<script><evil></script>'
    e = r'<script>/*<![CDATA[*/ < /*]]>*/evil/*<![CDATA[*/ > /*]]>*/</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_unexpected_tag_in_dqstring():
    s = r'<script>document.write("<b>");</script>'
    e = r'<script>document.write("\x3cb\x3e");</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_unexpected_tag_in_sqstring():
    s = r"<script>document.write('<b>');</script>"
    e = r"<script>document.write('\x3cb\x3e');</script>"
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_unexpected_tag_in_block_comment():
    s = r"<script>/* <evil> */</script>"
    e = r"<script>/* <![CDATA[<]]>evil<![CDATA[>]]> */</script>"
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_script_cdata_unexpected_eof_escapes_contained_tags():
    s = r'<script><evil>'
    e = r'<script>/*<![CDATA[*/ < /*]]>*/evil/*<![CDATA[*/ > /*]]>*/</script>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_space_before_tag_name():
    s = r"< p>"
    e_exc = 'Malformed tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
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
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_doctype_is_uppercased():
    s = r'<!doctype html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    e = r'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_bad_character_reference():
    s = r'<p>&#7;</p>'
    e = r'<p>&amp;#7;</p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_repeated_attribute():
    s = r"<p><div style='margin-top: 0px' id=x style='margin-left: 0px' />"
    e_exc = 'Repeated attribute "style" at line 1, column 38 (char 38)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_attribute_minimization():
    s = r'<option selected>'
    e = r'<option selected="selected"></option>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_junk_in_final_attribute():
    # Including the endslash is correct, we try to treat our input as HTML.
    s = r'<p x=:;"/><img>'
    e = r'<p x=":;&quot;/"><img /></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_one_colon_in_name():
    s = r'<py:test xmlns:py="..."/>'
    e = r'<py:test xmlns:py="..."/>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_two_colons_in_name():
    s = r'<a:b:c/>'
    e_exc = r'Malformed tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_closing_tags_at_end():
    s = r'this<p>is<a href="..">a test'
    e = r'this<p>is<a href="..">a test</a></p>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_html_gets_xmlns_attribute():
    s = r'<html><body>Test'
    e = r'<html xmlns="http://www.w3.org/1999/xhtml"><body>Test</body></html>'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert False, exc
    else:
        assert r==e, r

def test_innards_re_not_exponential():
    s = '<abcdefh.ijklmnopqrst uvwxy z 0>'
    e_exc = r'Malformed tag at line 1, column 1 (char 1)'
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_sniffer():
    tests = [
        (r'',
         'UTF-8'),
        (r'''<?xml version='1.0' encoding='ISO-8859-1' ?>''',
         'ISO-8859-1'),
        (r'''<?xml version="1.0" encoding='ISO-8859-1' ?>''',
         'ISO-8859-1'),
        (r'''<?xml version="1.0" encoding='ISO-8859-1' standalone='no'?>''',
         'ISO-8859-1'),
        (r'''<?xml version='1.1' encoding="ISO-8859-1" standalone="yes" ?>''',
         'ISO-8859-1'),
        (r'''<?xml version="1.0" encoding="EBCDIC-some-cp" ?>'''.encode('cp037'),
         'EBCDIC-some-cp'),
        # and now the really viciously pedantic refusals...
        (r''' <?xml version="1.0" encoding="ISO-8859-1" ?>''',
         'UTF-8'),  # bad: space before decl
        (r'''<?xml version=1.0 encoding="ISO-8859-1" ?>''',
         'UTF-8'),  # bad: no quotes around version value
        (r'''<?xml encoding="ISO-8859-1" version="1.0" ?>''',
         'UTF-8'),  # bad: wrong order for attributes
        (r'''<?xml version="1.0" encoding="ISO-8859-1" standalone=no ?>''',
         'UTF-8'),  # bad: no quotes around standalone value
        (r'''<?xml version=" 1.0" encoding="ISO-8859-1" ?>''',
         'UTF-8'),  # bad: whitespace before version value
        (r'''<?xml version="1.0 " encoding="ISO-8859-1" ?>''',
         'UTF-8'),  # bad: whitespace after version value
        (r'''<?xml version="1.0" encoding=" ISO-8859-1" ?>''',
         'UTF-8'),  # bad: whitespace before encoding value
        (r'''<?xml version="1.0" encoding="ISO-8859-1 " ?>''',
         'UTF-8'),  # bad: whitespace after encoding value
        (r'''<?xml version="1.0" encoding=Big5 ?>''',
         'UTF-8'),  # bad: no quotes around encoding value
    ]
    for i, (s, e) in enumerate(tests):
        try:
            r = sniff_encoding(s)
        except ValidationError as exc:
            assert False, (exc, i)
        else:
            assert r==e, (r, i)

def test_sniffer_exc():
    s = six.u('<?xml version="1.0" encoding="Cp037" ?>').encode('utf-8-sig')
    e_exc = r'Multiply-specified encoding (BOM: utf_8_sig, XML decl: Cp037) at line 1, column 1 (char 1)'
    try:
        r = sniff_encoding(s)
    except ValidationError as exc:
        assert str(exc)==e_exc, exc
    else:
        assert False, r

def test_fix_xmldecl():
    # Slow compared to the other tests, but still only a few seconds.
    for encoding in encodings.aliases.aliases.values():
        if encoding in ('rot_13', 'quopri_codec', 'zlib_codec',
                        'base64_codec', 'uu_codec', 'tactis',
                        'hex_codec', 'bz2_codec'):
            continue
        try:
            ''.encode(encoding)
        except LookupError:  # not trying to handle unknown encodings yet
            continue
        xmldecl = fix_xmldecl(six.u('  <?xml>').encode(encoding), encoding,
                              add_encoding=True)
        if encoding.lower().startswith('utf'):
            if '16' in encoding:
                if 'le' in encoding.lower():
                    assert xmldecl.startswith(codecs.BOM_UTF16_LE)
                if 'be' in encoding.lower():
                    assert xmldecl.startswith(codecs.BOM_UTF16_BE)
        sniffed = sniff_encoding(xmldecl)
        assert sniffed==encoding, (xmldecl, encoding, sniffed)
        xmldecl = fix_xmldecl(six.u('  <?xml>').encode(encoding), encoding,
                              add_encoding=True)
        if encoding.lower().startswith('utf'):
            if '16' in encoding:
                if 'le' in encoding.lower():
                    assert xmldecl.startswith(codecs.BOM_UTF16_LE)
                if 'be' in encoding.lower():
                    assert xmldecl.startswith(codecs.BOM_UTF16_BE)
        sniffed = sniff_encoding(xmldecl)
        assert sniffed==encoding, (xmldecl, encoding, sniffed)

def test_formfeed_in_xmldecl():
    xmldecl = fix_xmldecl(' \f\t\f\n\f\r\f<?xml>'.encode('utf16'))
    assert xmldecl.decode('utf16')=="<?xml version='1.0'?>", xmldecl
    xmldecl = fix_xmldecl((' \f\t\f\n\f\r\f<?xml\fversion="1.0"'
                           '\f\fstandalone=no\f\f?>').encode('utf16'))
    assert xmldecl.decode('utf16')==(
        '''<?xml version="1.0"  standalone='no'  ?>'''), xmldecl

def test_xhtmlify_handles_utf8_xmldecl():
    result = xhtmlify(six.u('<?xml><html>'), 'utf-8', _wrap=False)
    assert result==six.u('<?xml version=\'1.0\'?><html xmlns="http://www.w3.org/1999/xhtml"></html>')
    result = xhtmlify(six.u('<?xml><html>').encode('utf-8'), 'utf-8',
                      _wrap=False)
    assert result.decode('utf-8')==six.u('<?xml version=\'1.0\'?><html xmlns="http://www.w3.org/1999/xhtml"></html>')

def test_xhtmlify_handles_utf16_xmldecl():
    result = xhtmlify(six.u('<?xml><html>'), 'utf_16_be', _wrap=False)
    assert result==six.u('<?xml version=\'1.0\'?><html xmlns="http://www.w3.org/1999/xhtml"></html>')
    result = xhtmlify(six.u('<?xml><html>').encode('utf_16_be'), 'utf_16_be',
                      _wrap=False)
    assert result.decode('utf16')==six.u('<?xml version=\'1.0\'?><html xmlns="http://www.w3.org/1999/xhtml"></html>')

def test_doctype():
    s = r'''<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html>
    <head><title>test</title></head><body></body></html>'''
    e = r'''<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head><title>test</title></head><body></body></html>'''
    r = xhtmlify(s)
    assert r==e, r

def test_double_doctype():
    s = DOCTYPE_XHTML1_STRICT + DOCTYPE_XHTML1_STRICT
    assert s.split('\n')[1].startswith('<!DOCTYPE ')
    assert s[110:].startswith('<!DOCTYPE ')
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc).startswith(
            'Malformed tag at line 2, column 1 (char 111)'), exc
    else:
        assert False, r

def test_embedded_doctype():
    s = DOCTYPE_XHTML1_STRICT + '<html><head>' + DOCTYPE_XHTML1_STRICT
    assert s.split('\n')[1][12:].startswith('<!DOCTYPE ')
    assert s[122:].startswith('<!DOCTYPE '), s[122:]
    try:
        r = xhtmlify(s)
    except ValidationError as exc:
        assert str(exc).startswith(
            'Malformed tag at line 2, column 13 (char 123)'), exc
    else:
        assert False, r

def test_complex_doctype():
    s = r'''<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE html
        PUBLIC "-//W3C//DTD XHTML 1.1//EN"
               "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd"
    [
        <!ATTLIST form autocomplete CDATA #IMPLIED>
    ]>
    <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head><title /></head><body/></html>'''
    assert _xhtmlify(s)==s

def test_xhtml_appendix_b_prohibitions():
    prohibitions = {
        'a': ['a'],
        'pre': ['img', 'object', 'big', 'small', 'sub', 'sup'],
        'button': ['input', 'select', 'textarea', 'label', 'button',
                   'form', 'fieldset', 'iframe', 'isindex'],
        'label': ['label'],
        'form': ['form'],
    }
    for parent in prohibitions:
        for child in prohibitions[parent]:
            s = '<%s><p><%s>' % (parent, child)
            if child==parent:
                e_exc = ("XHTML <%s> elements must not "
                         "contain other <%s> elements")
            else:
                e_exc = ("XHTML <%s> elements must not "
                         "contain <%s> elements")
            e_exc %= (parent, child)
            try:
                r = xhtmlify(s)
            except ValidationError as e:
                assert str(e).startswith(e_exc + ' at line 1'), (s, e)
            else:
                assert False, (s, r)

def test_fieldset_nesting():
    s = '<fieldset><fieldset></fieldset></fieldset>'
    e = s
    r = xhtmlify(s)
    assert r==e, repr(r)

def test_sup_nesting():
    s = '<sup><sup></sup></sup>'
    e = s
    r = xhtmlify(s)
    assert r==e, repr(r)
