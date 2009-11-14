#!/usr/bin/env python
"""An HTML to XHTML converter."""
import re, htmlentitydefs


__all__ = ['xhtmlify', 'xmldecl', 'sniff_encoding', 'ValidationError']

DEBUG = False  # if true, show stack of tags in error messages
NAME_RE = r'(?:[A-Za-z_][A-Za-z0-9_.-]*(?::[A-Za-z_][A-Za-z0-9_.-]*)?)'
    # low ascii chars of <http://www.w3.org/TR/xml-names>'s "QName" token
BAD_ATTR_RE = r'''[^> \t\r\n]+'''
ATTR_RE = r'''%s[ \t\r\n]*(?:=[ \t\r\n]*(?:"[^"]*"|'[^']*'|%s))?''' % (NAME_RE, BAD_ATTR_RE)
CDATA_RE = r'<!\[CDATA\[.*?\]\]>'
COMMENT_RE = r'<!--.*?-->|<![ \t\r\n]*%s.*?>' % NAME_RE # comment or doctype-alike
TAG_RE = r'''%s|%s|<((?:[^<>'"]+|'[^']*'|"[^"]*"|'|")*)>|<''' % (COMMENT_RE, CDATA_RE)
INNARDS_RE = r'(%s(?:[ \t\r\n]+%s)*[ \t\r\n]*(/?)\Z)|(/%s[ \t\r\n]*\Z)|(.*)' % (
                 NAME_RE, ATTR_RE, NAME_RE)

SELF_CLOSING_TAGS = [
    # As per XHTML 1.0 sections 4.6, C.2 and C.3, these are the elements
    # in the XHTML 1.0 DTDs marked "EMPTY".
    'base', 'meta', 'link', 'hr', 'br', 'param', 'img', 'area',
    'input', 'col', 'isindex', 'basefont', 'frame'
]
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
    Adapted from <http://effbot.org/zone/re-sub.htm#unescape-html>.
    Also converts all entities to numeric form and replaces any
    unmatched "]]>"s with "]]&gt;"."""
    def fixup(m):
        text = m.group(0)
        if text=='&':
            pass
        elif text[:2] == "&#":
            # character reference
            try:
                if text[:3] in ("&#x", "&#X"):
                    c = unichr(int(text[3:-1], 16))
                else:
                    c = unichr(int(text[2:-1], 10))
            except ValueError:
                pass
            else:
                # "&#X...;" is invalid in XHTML
                c = ord(c)
                if c in (0x9, 0xA, 0xD) or 0x0020<=c<=0xD7FF or (
                   0xE000<=c<=0xFFFD) or 0x10000<=c<=0x10FFFF: 
                    return text.lower()  # well-formed
                else:
                    pass
        else:
            # Named entity. So that no external DTDs are needed
            # for validation, we only preserve XML hard-coded
            # named entities.
            name = text[1:-1]
            if name in ['amp', 'lt', 'gt', 'quot', 'apos']:
                return text
            else:
                cp = htmlentitydefs.name2codepoint.get(name)
                if cp:
                    return '&#x%x;' % cp
                else:
                    pass
        return '&amp;' + text[1:]
    value = re.compile('(<!\[CDATA\[.*?\]\]>)|\]\]>', re.DOTALL).sub(
        (lambda m: m.group(1) or "]]&gt;"), value)
    return re.sub("&#?\w+;|&", fixup, value)

def fix_attrs(tagname, attrs, ERROR=None):
    """Returns an XHTML-clean version of attrs, the attributes part
       of an (X)HTML tag. Tries to make as few changes as possible,
       but does convert all attribute names to lowercase."""
    if not attrs and tagname!='html':
        return ''  # most tags have no attrs, quick exit in that case
    lastpos = 0
    result = []
    output = result.append
    seen = {}  # enforce XML's "Well-formedness constraint: Unique Att Spec"
    for m in re.compile(ATTR_RE, re.DOTALL).finditer(attrs):
        output(attrs[lastpos:m.start()])
        lastpos = m.end()
        attr = m.group()
        if '=' not in attr:
            assert re.compile(NAME_RE + r'[ \t\r\n]*\Z').match(attr), repr(attr)
            output(re.sub('(%s)' % NAME_RE, r'\1="\1"', attr).lower())
        else:
            name, value = attr.split('=', 1)
            name = name.lower()
            if name in seen:
                ERROR('Repeated attribute "%s"' % name)
            else:
                seen[name] = 1
            if len(value)>1 and value[0]+value[-1] in ("''", '""'):
                if value[0] not in value[1:-1]:  # preserve their quoting
                    output('%s=%s' % (name, ampfix(value).replace('<', '&lt;')))
                    continue
                value = value[1:-1]
            output('%s="%s"' % (name, ampfix(value.replace('"', '&quot;')
                                                  .replace('<', '&lt;'))))
    output(attrs[lastpos:])
    if tagname=='html' and 'xmlns' not in seen:
        output(' xmlns="http://www.w3.org/1999/xhtml"')
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

def xmldecl(version='1.0', encoding=None, standalone=None):
    """Returns a valid <?xml ...?> declaration suitable for using
       at the start of a document. Note that no other characters are
       allowed before the declaration (other than byte-order markers).
       Only set standalone if you really know what you're doing.
       Raises a ValidationError if given invalid values."""
    if not re.match(r'1\.[0-9]+\Z', version):
        raise ValidationError('Bad version in XML declaration',
                              0, 1, 1, [])
    encodingdecl = ''
    if encoding:
        if re.match(r'[A-Za-z][A-Za-z0-9._-]*\Z', encoding):
            encodingdecl = ' encoding="%s"' % encoding
        else:
            # Don't tell them expected format, guessing won't help
            raise ValidationError('Bad encoding name in XML declaration',
                                  0, 1, 1, [])
    sddecl = ''
    if standalone:
        if re.match('(?:yes|no)\Z', standalone):
            sddecl = ' standalone="%s"' % standalone
        else:
            # Don't tell them expected format, guessing won't help
            raise ValidationError('Bad standalone value in XML declaration',
                                  0, 1, 1, [])
    return '<?xml version="%s"%s%s ?>' % (version, encodingdecl, sddecl)

def fix_xmldecl(html):
    """Looks for an XML declaration near the start of html, cleans it up,
       and returns the adjusted version of html. Doesn't add a declaration
       if none was found."""
    m = re.match(r'(?si)(?:\s+|<!--.*?-->)*(<\?xml\s[^>]*>\s*)', html)
    if not m:
        return html
    else:
        before, decl, after = html[:m.start(1)], m.group(1), html[m.end(1):]
        m = re.search(
            r'''(?ui)\sversion\s*=\s*'([^']*)'|"([^"]*)"|([^\s<>]*)''', decl)
        if m:
            if m.group(1) is not None:
                g = 1
            elif m.group(2) is not None:
                g = 2
            else:
                g = 3
            if re.match(r'1\.[0-9]+\Z', m.group(g)):
                version = m.group()
            else:
                raise ValidationError('Bad version in XML declaration',
                                      0, 1, 1, [])
        return decl + before + after

def xhtmlify(html, encoding='UTF-8',
                   self_closing_tags=SELF_CLOSING_TAGS,
                   cdata_tags=CDATA_TAGS,
                   structural_tags=STRUCTURAL_TAGS):
    """
    Parses HTML and converts it to XHTML-style tags.
    Raises a ValidationError if the tags are badly nested or malformed.
    It is slightly stricter than normal HTML in some places and more lenient
    in others, but it generally tries to behave in a human-friendly way.
    It is intended to be idempotent, i.e. it should make no changes if fed
    its own output. It accepts XHTML-style self-closing tags.
    """
    html = fix_xmldecl(html)
    if not encoding:
        encoding = sniff_encoding(html)
    unicode_input = isinstance(html, unicode)
    if unicode_input:
        html = html.encode(encoding, 'strict')
    if not isinstance(html, str):
        raise TypeError("Expected string, got %s" % type(html))
    html = html.decode(encoding, 'replace')
    # "in HTML, the Formfeed character (U+000C) is treated as white space"
    html = html.replace(u'\u000C', u' ')
    # Replace disallowed characters with U+FFFD (unicode replacement char)
    html = re.sub(  # XML 1.0 section 2.2, "Char" production
        u'[^\x09\x0A\x0D\u0020-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]',
        u'\N{replacement character}', html)

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
            whole_tag = tag_match.group()
            if whole_tag.startswith('<!'):
                # CDATA, comment, or doctype-alike. Treat as text.
                if re.match(r'(?i)<!doctype[ \t\r\n]', whole_tag):
                    output('<!DOCTYPE')
                    lastpos += 9
                continue
            assert whole_tag=='<'
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
            tagname = TagName.lower()
            attrs = fix_attrs(tagname, attrs, ERROR=ERROR)
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
        elif m.group(4): # mismatch
            ERROR("Malformed tag")
        else:
            # We don't do any validation on pre-processing tags (<? ... >).
            output(ampfix(tag_match.group()))
        lastpos = tag_match.end()
    output(ampfix(html[lastpos:]))
    while tags:
        TagName, pos = tags.pop()
        tagname = TagName.lower()
        if tagname not in self_closing_tags:
            output('</%s>' % tagname)
    result = ''.join(result)
    if not unicode_input:
        # There's an argument that we should only ever deal in bytes,
        # but it's probably more helpful to say "unicode in => unicode out".
        result = result.encode(encoding)
    return result

def test(html=None):
    if html is None:
        import sys
        if len(sys.argv)==2:
            if sys.argv[1]=='-':
                html = sys.stdin.read()
            else:
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

def sniff_encoding(xml):
    """Detects the XML encoding as per XML 1.0 section F.1."""
    enc = sniff_bom_encoding(xml)
    # Now the fun really starts. We compile the encoded sniffer regexp.
    L = lambda s: re.escape(s.encode(enc))  # encoded form of literal s
    optional = lambda s: '(?:%s)?' % s
    oneof = lambda opts: '(?:%s)' % '|'.join(opts)
    charset = lambda s: oneof([L(c) for c in s])
    upper = charset('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    lower = charset('abcdefghijklmnopqrstuvwxyz')
    digits = charset('0123456789')
    punc = charset('._-')
    name = '(?:%s%s*)' % (oneof([upper, lower]), 
                          oneof([upper, lower, digits, punc]))
    Ss = charset(' \t\r\n')+'*'  # optional white space
    Sp = charset(' \t\r\n')+'+'  # required white space
    Eq = ''.join([Ss, L('='), Ss])
    VersionInfo = ''.join([
        Sp, L('version'), Eq, oneof([L("'1.")+digits+L("'"),
                                     L('"1.')+digits+L('"')]) ])
    # standalone="yes" is valid XML but almost certainly a lie...
    SDDecl = ''.join([
        Sp, L('standalone'), Eq, oneof([L("'")+oneof(['yes', 'no'])+L("'"),
                                        L('"')+oneof(['yes', 'no'])+L('"')])])
    R = ''.join([
        L('<?xml'), optional(VersionInfo),
        Sp, L('encoding'), Eq, '(?P<enc>%s|%s)' % (
            L("'")+name+L("'"), L('"')+name+L('"')),
        optional(SDDecl),
        Ss, L('?>') ])
    m = re.match(R, xml)
    if m:
        decl_enc = m.group('enc')[1:-1]
        if (enc==enc.lower() and
            codecs.lookup(enc) != codecs.lookup(decl_enc.lower)):
                return ValidationError(
                    "Multiply-specified encoding (BOM=>%r, XML decl'=>%r)" %
                        (enc, decl_enc),
                    0, 1, 1, [])
        return decl_enc
    else:
        return 'UTF-8'

def sniff_bom_encoding(xml):
    """Reads any byte-order marker. Returns the implied encoding.
       If the returned encoding is lowercase it means the BOM uniquely
       identified an encoding, so we don't need to parse the <?xml...?>
       to extract the encoding in theory."""
    enc = {
        '\x00\x00\xFE\xFF': 'utf_32_be', #UCS4 1234
        '\xFF\xFE\x00\x00': 'utf_32_le', #UCS4 4321
        '\x00\x00\xFF\xFE': 'undefined', #UCS4 2143 (rare, we give up)
        '\xFE\xFF\x00\x00': 'undefined', #UCS4 3412 (rare, we give up)
        '\x00\x00\x00\x3C': 'UTF_32_BE', #UCS4 1234 (no BOM)
        '\x3C\x00\x00\x00': 'UTF_32_LE', #UCS4 4321 (no BOM)
        '\x00\x00\x3C\x00': 'undefined', #UCS4 2143 (no BOM, we give up)
        '\x00\x3C\x00\x00': 'undefined', #UCS4 3412 (no BOM, we give up)
        '\x00\x3C\x00\x3F': 'UTF_16_BE',
        '\x3C\x00\x3F\x00': 'UTF_16_LE',
        '\x3C\x3F\x78\x6D': 'ASCII',
        '\x4C\x6F\xA7\x94': 'EBCDIC',
    }.get(xml[:4])
    if enc and enc==enc.lower():
        return enc
    if not enc:
        if xml[:3]=='\xEF\xBB\xBF':
            return 'utf_8_sig'  # UTF-8 with these three bytes prefixed
        elif xml[:2]=='\xFF\xFE':
            return 'utf_16_le'
        elif xml[:2]=='\xFE\xFF':
            return 'utf_16_be'
        else:
            enc = 'UTF-8'  # "Other"
    return enc

if __name__=='__main__':
    test()

