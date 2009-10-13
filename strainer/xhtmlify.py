#!/usr/bin/env python
"""An HTML to XHTML converter."""
import re, htmlentitydefs


__all__ = ['xhtmlify', 'ValidationError']

DEBUG = False  # if true, show stack of tags in error messages
NAME_RE = r'(?:[_a-zA-Z\-][_a-zA-Z0-9\-]*(?::[_a-zA-Z\-][_a-zA-Z0-9\-]*)?)'
BAD_ATTR_RE = r'''[^<>\s"'][^<>\s]*'''
ATTR_RE = r'''%s\s*(?:=\s*(?:".*?"|'.*?'|%s))?''' % (NAME_RE, BAD_ATTR_RE)
CDATA_RE = r'<!\[CDATA\[.*?\]\]>'
COMMENT_RE = r'<!--.*?-->|<!\s*%s.*?>' % NAME_RE # comment or doctype-alike
TAG_RE = r'%s|%s|<([^<>]*)>|<' % (COMMENT_RE, CDATA_RE)
INNARDS_RE = r'(%s\s*(?:%s\s*)*(/?)\Z)|(/%s\s*\Z)|(\?.*)|(.*)' % (
                 NAME_RE, ATTR_RE, NAME_RE)

SELF_CLOSING_TAGS = ['br', 'hr', 'input', 'img', 'meta',
                     'spacer', 'link', 'frame', 'base'] # from BeautifulSoup
CDATA_TAGS = ['script', 'style']
# "Structural tags" are those that cause us to auto-close any open <p> tag.
# This is hard to get right. Useful URLs to consult:
#   * http://htmlhelp.com/reference/html40/block.html
#   * http://www.cs.tut.fi/~jkorpela/html/nesting.html
#   * http://validator.w3.org/
STRUCTURAL_TAGS = [
    # 'center', # no such tag in XHTML, but we allow it anywhere
    # 'div', # can contain anything, anything can contain div
    # 'noframes', 'noscript', # deliberately ignoring these
    'address', 'blockquote', 'dir', 'dl', 'fieldset', 'form',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'isindex', 'menu',
    'ol', 'p', 'pre', 'table', 'ul',
    'section', 'article', 'aside', 'header', 'footer', 'nav'  # HTML 5
]

class ValidationError(Exception):
    def __init__(self, message, pos, line, offset, tags):
        message += ' at line %d, column %d (char %d)' % (line, offset, pos+1)
        if DEBUG:
            message += '\n%r' % tags
        super(ValidationError, self).__init__(message)
        self.pos = pos
        self.line = line
        self.offset = offset

def ampfix(value):
    """Replaces ampersands in value that aren't part of an HTML entity.
    Adapted from <http://effbot.org/zone/re-sub.htm#unescape-html>."""
    def fixup(m):
        text = m.group(0)
        if text=='&':
            pass
        elif text[:2] == "&#":
            # character reference
            try:
                if text[:3] in ("&#x", "&#X"):
                    unichr(int(text[3:-1], 16))
                else:
                    unichr(int(text[2:-1], 10))
            except ValueError:
                pass
            else:
                # "&#X...;" is invalid in XHTML
                return text.lower()  # well-formed
        else:
            # named entity
            try:
                return '&#%d;' % htmlentitydefs.name2codepoint[text[1:-1]]
            except KeyError:
                pass
        return '&#38;' + text[1:]
    return re.sub("&#?\w+;|&", fixup, value)

def fix_attrs(attrs):
    """Returns an XHTML-clean version of attrs, the attributes part
       of an (X)HTML tag. Tries to make as few changes as possible,
       but does convert all attribute names to lowercase."""
    if not attrs:
        return ''  # most tags have no attrs, quick exit in that case
    lastpos = 0
    result = []
    output = result.append
    for m in re.compile(ATTR_RE, re.DOTALL).finditer(attrs):
        output(attrs[lastpos:m.start()])
        lastpos = m.end()
        attr = m.group()
        if '=' not in attr:
            assert re.compile(NAME_RE + r'\s*\Z').match(attr), repr(attr)
            output(re.sub('(%s)' % NAME_RE, r'\1="\1"', attr).lower())
        else:
            name, value = attr.split('=', 1)
            name = name.lower()
            if len(value)>1 and value[0]+value[-1] in ("''", '""'):
                if value[0] not in value[1:-1]:  # preserve their quoting
                    output('%s=%s' % (name, ampfix(value)))
                    continue
                value = value[1:-1]
            output('%s="%s"' % (name, ampfix(value.replace('"', '&quot;'))))
    output(attrs[lastpos:])
    return ''.join(result)

def cdatafix(value):
    """Alters value, the body of a <script> or <style> tag, so that
       it will be parsed equivalently by the underlying language parser
       whether it is treated as containing CDATA (by an XHTML parser)
       or #PCDATA (by an HTML parser).
    """
    cdata_re = re.compile('(%s)' % CDATA_RE, re.DOTALL)
    result = []
    output = result.append
    outside_lexer  = re.compile(r'''((/\*|"|')|(<!\[CDATA\[)|(\]\]>)|\]|(<)|(>)|(&))|/|[^/"'<>&\]]+''')
    comment_lexer  = re.compile(r'''((\*/)|(<!\[CDATA\[)|(\]\]>)|(<)|\]|(>)|(&))|\*|[^\*<>&\]]+''')
    dqstring_lexer = re.compile(r'''\\.|((")|(<!\[CDATA\[)|(\]\]>)|\]|(\\<|<)|(\\>|>)|(\\&|&))|[^\\"<>&\]]+''', re.DOTALL)
    sqstring_lexer = re.compile(r'''\\.|((')|(<!\[CDATA\[)|(\]\]>)|\]|(\\<|<)|(\\>|>)|(\\&|&))|[^\\'<>&\]]+''', re.DOTALL)
    Outside, Comment, DQString, SQString = [], [], [], []
    Outside += (outside_lexer.match,
                '/*<![CDATA[*/ < /*]]>*/',
                '/*<![CDATA[*/ > /*]]>*/',
                '/*<![CDATA[*/ & /*]]>*/',
                {'/*': Comment, '"': DQString, "'": SQString})
    Comment += (comment_lexer.match,
                '<![CDATA[<]]>',
                '<![CDATA[>]]>',
                '<![CDATA[&]]>',
                {'*/': Outside})
    DQString += (dqstring_lexer.match,
                r'\x3c',
                r'\x3e',
                r'\x26',
                {'"': Outside})
    SQString += (sqstring_lexer.match,
                r'\x3c',
                r'\x3e',
                r'\x26',
                {"'": Outside})
    #names = dict(zip([x[0] for x in Outside, Comment, DQString, SQString],
    #                       ['Outside', 'Comment', 'DQString', 'SQString']))
    lexer, lt_rep, gt_rep, amp_rep, next_state = Outside
    pos = 0
    in_cdata = False
    while pos < len(value):
        m = lexer(value, pos)
        #print '%s:' % names[lexer], 'in_cdata=%d' % in_cdata, repr(m.group())
        assert m.start()==pos  # no gaps
        pos = m.end()
        (interesting, state_changer, cdata_start, cdata_end,
         lt, gt, amp) = m.groups()
        if interesting:
            if cdata_start:
                output(m.group())
                in_cdata = True
            elif cdata_end:
                if in_cdata:
                    output(m.group())
                else:
                    output(']]')
                    pos = m.start()+2  # so > gets escaped as normal
                in_cdata = False
            elif lt:
                output(in_cdata and m.group() or lt_rep)
            elif gt:
                output(in_cdata and m.group() or gt_rep)
            elif amp:
                output(in_cdata and m.group() or amp_rep)
            elif m.group()==']':
                output(']')
            else:
                output(in_cdata and m.group() or state_changer)
                lexer, lt_rep, gt_rep, amp_rep, next_state = next_state[state_changer]
        else:
            output(m.group())
    assert not in_cdata  # enforced by calling parser (I think)
    return ''.join(result)

def xhtmlify(html, self_closing_tags=SELF_CLOSING_TAGS,
                   cdata_tags=CDATA_TAGS,
                   structural_tags=STRUCTURAL_TAGS):
    """
    Parses HTML and converts it to XHTML-style tags.
    Throws a ValidationError if the tags are badly nested or malformed.
    It is slightly stricter than normal HTML in some places and more lenient
    in others, but it generally behaves in a human-friendly way.
    It is intended to be idempotent, i.e. it should make no changes if fed its
    own output. This implies that it accepts XHTML-style self-closing tags.
    """
    def ERROR(message, charpos=None):
        if charpos is None:
            charpos = pos
        line = html.count('\n', 0, charpos)+1
        offset = charpos - html.rfind('\n', 0, charpos)
        raise ValidationError(message, charpos, line, offset, tags)

    for tag in cdata_tags:
        assert tag not in self_closing_tags
    assert 'div' not in structural_tags  # can safely nest with <p>s
    assert 'span' not in structural_tags
    # ... but 'p' can be in structural_tags => disallow nested <p>s.
    tags = []
    result = []
    output = result.append
    lastpos = 0
    tag_re = re.compile(TAG_RE, re.DOTALL | re.IGNORECASE)
    for tag_match in tag_re.finditer(html):
        pos = tag_match.start()
        prevtag = tags and tags[-1][0].lower() or None
        innards = tag_match.group(1)
        if innards is None:
            if tag_match.group().startswith('<!'):
                continue  # CDATA, comment, or doctype-alike. Treat as text.
            assert tag_match.group()=='<'
            if prevtag in cdata_tags:
                continue  # ignore until we have all the text
            else:
                ERROR('Unescaped "<" or unfinished tag')
        elif not innards:
            ERROR("Empty tag")
        text = html[lastpos:pos]
        if prevtag in cdata_tags:
            output(cdatafix(text))
        else:
            output(ampfix(text))
        m = re.compile(INNARDS_RE, re.DOTALL).match(innards)
        if prevtag in cdata_tags and (not m.group(3) or
            re.match(r'/(%s)' % NAME_RE, innards).group(1).lower()!=prevtag):
            # not the closing tag, output it as CDATA
            output('<![CDATA[%s]]>' % tag_match.group()
                                        .replace(']]>', ']]]]><![CDATA[>'))
        elif m.group(1): # opening tag
            endslash = m.group(2)
            m = re.match(NAME_RE, innards)
            TagName, attrs = m.group(), innards[m.end():]
            attrs = fix_attrs(attrs)
            tagname = TagName.lower()
            if prevtag in self_closing_tags:
                tags.pop()
                prevtag = tags and tags[-1][0].lower() or None
            # No tags other than <div> and <span> can self-nest (I think)
            # and we automatically close <p> tags before structural tags.
            if (tagname==prevtag and tagname not in ('div', 'span')) or (
                prevtag=='p' and tagname in structural_tags):
                tags.pop()
                output('</%s>' % prevtag)
                #prevtag = tags and tags[-1][0].lower() or None  # not needed
            if endslash:
                output('<%s%s>' % (tagname, attrs))
            elif tagname in self_closing_tags:
                if attrs.rstrip()==attrs:
                    attrs += ' '
                output('<%s%s/>' % (tagname, attrs))  # preempt any closing tag
                tags.append((TagName, pos))
            else:
                output('<%s%s>' % (tagname, attrs))
                tags.append((TagName, pos))
        elif m.group(3): # closing tag
            TagName = re.match(r'/(\w+)', innards).group(1)
            tagname = TagName.lower()
            if prevtag in self_closing_tags:
                # The tag has already been output in self-closed form.
                if prevtag==tagname: # explicit close
                    # Minor hack: discard any whitespace we just output
                    if result[-1].strip():
                        ERROR("Self-closing tag <%s/> is not empty" %
                                  tags[-1][0], tags[-1][1])
                    else:
                        result.pop()
                else:
                    tags.pop()
                    prevtag = tags and tags[-1][0].lower() or None
                    assert prevtag not in self_closing_tags
            # If we have found a mismatched close tag, we may insert
            # a close tag for the previous tag to fix it in some cases.
            # Specifically, closing a container can close an open child.
            if prevtag!=tagname and (
                 (prevtag=='p' and tagname in structural_tags) or
                 (prevtag=='li' and tagname in ('ol', 'ul')) or
                 (prevtag=='dd' and tagname=='dl') or
                 (prevtag=='area' and tagname=='map') or
                 (prevtag=='td' and tagname=='tr') or
                 (prevtag=='th' and tagname=='tr')
            ):
                output('</%s>' % prevtag)
                tags.pop()
                prevtag = tags and tags[-1][0].lower() or None
            if prevtag==tagname:
                if tagname not in self_closing_tags:
                    output(tag_match.group().lower())
                    tags.pop()
            else:
                ERROR("Unexpected closing tag </%s>" % TagName)
        elif m.group(5): # mismatch
            ERROR("Malformed tag")
        else:
            # We don't do any validation on pre-processing tags (<? ... >).
            output(ampfix(tag_match.group()))
        lastpos = tag_match.end()
    while tags:
        TagName, pos = tags.pop()
        tagname = TagName.lower()
        if tagname not in self_closing_tags:
            output('</%s>' % tagname)
    output(ampfix(html[lastpos:]))
    return ''.join(result)

def test(html=None):
    if html is None:
        import sys
        if len(sys.argv)==2:
            html = open(sys.argv[1]).read()
        else:
            sys.exit('usage: %s HTMLFILE' % sys.argv[0])
    xhtml = xhtmlify(html)
    try:
        assert xhtml==xhtmlify(xhtml)
    except ValidationError:
        print xhtml
        raise
    xmlparse(re.sub('(?s)<!(?!\[).*?>', '', xhtml))  # ET can't handle <!...>
    if len(sys.argv)==2:
        print xhtml
    return xhtml

def xmlparse(snippet):
    """Parse snippet as XML without an outer document element
       with ElementTree/expat."""
    import xml.parsers.expat
    from xml.etree import ElementTree as ET
    try:
        try:
            parser = ET.XMLParser(encoding='utf-8')
        except TypeError:
            parser = ET.XMLParser()  # old version
        input = '<document>\n%s\n</document>' % snippet
        parser.feed(input)
        parser.close()
    except xml.parsers.expat.ExpatError, e:
        lineno, offset = e.lineno, e.offset
        lineno -= 1
        if lineno==input.count('\n'):  # last line => </document>
            lineno -= 1
            offset = len(snippet) - snippet.rfind('\n')
        message = re.sub(r'line \d+', 'line %d' % lineno,
                         e.message, count=1)
        message = re.sub(r'column \d+', 'column %d' % offset,
                         message, count=1)
        parse_error = xml.parsers.expat.ExpatError(message)
        parse_error.lineno = lineno
        parse_error.offset = offset
        parse_error.code = e.code
        raise parse_error

if __name__=='__main__':
    test()

