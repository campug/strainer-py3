#!/usr/bin/env python
"""An HTML to XHTML converter."""
from __future__ import print_function
import re

import codecs
import encodings.aliases
import six

from six.moves import html_entities as htmlentitydefs


__all__ = [
    'xhtmlify',
    'xmldecl',
    'fix_xmldecl',
    'sniff_encoding',
    'ValidationError',
]

# if true, show stack of tags in error messages
DEBUG = False
NAME_RE = r'(?:[A-Za-z_][A-Za-z0-9_.-]*(?::[A-Za-z_][A-Za-z0-9_.-]*)?)'
# low ascii chars of <http://www.w3.org/TR/xml-names>'s "QName" token
BAD_ATTR_RE = r'''[^> \t\r\n]+'''
ATTR_RE = r'''%s[ \t\r\n]*(?:=[ \t\r\n]*(?:"[^"]*"|'[^']*'|%s))?[ \t\r\n]*'''\
        % (NAME_RE, BAD_ATTR_RE)
CDATA_RE = r'<!\[CDATA\[.*?\]\]>'
# comment or doctype-alike
#COMMENT_RE = r'<!--.*?-->|<![ \t\r\n]*%s.*?>' % NAME_RE
COMMENT_RE = r'<!--.*?-->'
TAG_RE = r'''%s|%s|<((?:[^<>'"]+|'[^']*'|"[^"]*"|'|")*)>|<'''\
        % (COMMENT_RE, CDATA_RE)
INNARDS_RE = r'(%s(?:[ \t\r\n]+%s)*[ \t\r\n]*(/?)\Z)|(/%s[ \t\r\n]*\Z)|(.*)'\
        % (NAME_RE, ATTR_RE, NAME_RE)

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


class StrainerError(Exception):
    pass


class ValidationError(StrainerError):
    def __init__(self, message, pos, line, offset, tags):
        message += ' at line %d, column %d (char %d)' % (line, offset, pos + 1)
        if DEBUG:
            message += '\n%r' % tags
        super(ValidationError, self).__init__(message)
        self.pos = pos
        self.line = line
        self.offset = offset


class XMLParsingError(StrainerError):
    pass


def ampfix(value):
    """Replaces ampersands in value that aren't part of an HTML entity.
    Adapted from <http://effbot.org/zone/re-sub.htm#unescape-html>.
    Also converts all entities to numeric form and replaces every
    "<" or ">" outside of any CDATA sections with "&lt;" or "&gt;"."""
    def fixup(m):
        text = m.group(0)
        if text == '&':
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
                if c in (0x9, 0xA, 0xD) or 0x0020 <= c <= 0xD7FF or (
                   0xE000 <= c <= 0xFFFD) or 0x10000 <= c <= 0x10FFFF:
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

    def fix2(m):
        g = m.group()
        if g.startswith('<!'):
            return g
        elif g == '<':
            return '&lt;'
        elif g == '>':
            return '&gt;'
        else:
            return re.sub("&#?\w+;|&", fixup, g)
    R = re.compile('(<!\[CDATA\[.*?\]\]>)|<!--.*?-->|<|>|[^<>]+', re.DOTALL)
    return R.sub(fix2, value)


def fix_attrs(tagname, attrs, ERROR=None):
    """Returns an XHTML-clean version of attrs, the attributes part
       of an (X)HTML tag. Tries to make as few changes as possible,
       but does convert all attribute names to lowercase."""
    if not attrs and tagname != 'html':
        return ''  # most tags have no attrs, quick exit in that case
    lastpos = 0
    result = []
    output = result.append
    seen = {}  # enforce XML's "Well-formedness constraint: Unique Att Spec"
    name_re = re.compile('(%s)' % NAME_RE + r'([ \t\r\n]*)\Z')
    space_before = ' '
    for m in re.compile(ATTR_RE, re.DOTALL).finditer(attrs):
        assert re.match(r'[ \t\r\n]*\Z', attrs[lastpos:m.start()])
        output(attrs[lastpos:m.start()] or space_before)
        lastpos = m.end()
        attr = m.group()
        # A space to insert before the next attribute
        if attr[-1:] in ' \t\r\n':
            space_before = ''
        else:
            space_before = ' '
        if '=' not in attr:
            assert name_re.match(attr), repr(attr)
            output(re.sub(r'\A(%s)' % NAME_RE, r'\1="\1"', attr).lower())
        else:
            name, value = attr.split('=', 1)
            m2 = name_re.match(name)
            if m2:
                name, postname = m2.groups()
            else:
                ERROR("Invalid attribute name", m.start())
            name = name.lower()
            preval = re.match(r'[ \t\r\n]*', value).group()
            value = value[len(preval):]
            value_end = re.search(r'[ \t\r\n]*\Z', value).start()
            value, postval = value[:value_end], value[value_end:]
            if name in seen:
                ERROR('Repeated attribute "%s"' % name, m.start())
            else:
                seen[name] = 1

            if len(value) > 1 and value[0] + value[-1] in ("''", '""'):
                if value[0] not in value[1:-1]:  # preserve their quoting
                    value = ampfix(value)
                    output('%s%s=%s%s%s' % (
                        name, postname, preval, value, postval))
                    continue
                value = value[1:-1]
            value = ampfix(value.replace('"', '&quot;'))
            output('%s%s=%s"%s"%s' % (name, postname, preval, value, postval))
    after = attrs[lastpos:]
    if re.match(r'[ \t\r\n]*/?', after).end() == len(after):
        output(after)
    else:
        ERROR("Malformed tag contents", lastpos)

    if tagname == 'html' and 'xmlns' not in seen:
        output(space_before + 'xmlns="http://www.w3.org/1999/xhtml"')
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
    outside_lexer = re.compile(
        r'''((/\*|"|')|(<!\[CDATA\[)|(\]\]>)|\]|(<)|(>)|(&))|/|[^/"'<>&\]]+''')
    comment_lexer = re.compile(
        r'''((\*/)|(<!\[CDATA\[)|(\]\]>)|\]|(<)|(>)|(&))|\*|[^\*<>&\]]+''')
    dqstring_lexer = re.compile(
        r'''\\[^<>]|((")|(<!\[CDATA\[)|(\]\]>)|\]|(\\<|<)|(\\>|>)|(\\&|&))|[^\\"<>&\]]+''', re.DOTALL)
    sqstring_lexer = re.compile(
        r'''\\[^<>]|((')|(<!\[CDATA\[)|(\]\]>)|\]|(\\<|<)|(\\>|>)|(\\&|&))|[^\\'<>&\]]+''', re.DOTALL)
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
        assert m.start() == pos  # no gaps
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
                    pos = m.start() + 2  # so > gets escaped as normal
                in_cdata = False
            elif lt:
                output(in_cdata and m.group() or lt_rep)
            elif gt:
                output(in_cdata and m.group() or gt_rep)
            elif amp:
                output(in_cdata and m.group() or amp_rep)
            elif m.group() == ']':
                output(']')
            else:
                output(in_cdata and m.group() or state_changer)
                lexer, lt_rep, gt_rep, amp_rep, next_state = \
                        next_state[state_changer]
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
    if encoding is not None:
        EncName_re = re.compile(r'[A-Za-z][A-Za-z0-9._-]*\Z')  # from XML spec
        if isinstance(encoding, basestring) and EncName_re.match(encoding):
            encodingdecl = ' encoding="%s"' % encoding
        else:
            # Don't tell them expected format, guessing won't help
            raise ValidationError('Bad encoding name in XML declaration',
                                  0, 1, 1, [])
    sddecl = ''
    if standalone is not None:
        if standalone is True or standalone == 'yes':
            sddecl = ' standalone="yes"'
        elif standalone is False or standalone == 'no':
            sddecl = ' standalone="no"'
        else:
            # Don't tell them expected format, guessing won't help
            raise ValidationError('Bad standalone value in XML declaration',
                                  0, 1, 1, [])
    return '<?xml version="%s"%s%s ?>' % (version, encodingdecl, sddecl)


def fix_xmldecl(xml, encoding=None, add_encoding=False, default_version='1.0'):
    """Looks for an XML declaration near the start of xml, cleans it up,
       and returns the adjusted version of xml. Doesn't add a declaration
       if none was found."""
    # This code started as a copy of sniff_encoding(), which follows the
    # XML spec.  This version uses a more lenient parser.
    EOS = r'\Z'  # end of string regexp
    starts_utf16_re = re.compile('utf[_-]?16', re.IGNORECASE)
    bomless_utf16_re = re.compile('utf[_-]?16[_-]?[bl]e\Z', re.IGNORECASE)
    unicode_input = isinstance(xml, six.text_type)
    if not re.match(r'1\.[0-9]+' + EOS, default_version):
        raise ValueError("Bad default XML declaration version")
    if encoding is not None:
        # Use a more standard name for the encoding
        encoding = encodings.normalize_encoding(encoding)
        if encoding.lower() in encodings.aliases.aliases:
            encoding = encodings.aliases.aliases[encoding.lower()]
        if not re.match('[A-Za-z][A-Za-z0-9._-]*' + EOS, encoding):
            raise ValueError("Bad default XML declaration encoding")
        if starts_utf16_re.match(encoding):
            # XML spec 4.3.3 says "Entities encoded in UTF-16 MUST [...]
            # begin with the Byte Order Mark".
            if not unicode_input and not (
                xml.startswith(codecs.BOM_UTF16_LE) or
                xml.startswith(codecs.BOM_UTF16_BE)):

                xml = six.u('\ufeff').encode(encoding) + xml
            elif unicode_input and bomless_utf16_re.match(encoding):
                xml = six.u('\ufeff') + xml
            # "else: pass"; Python adds the BOM when encoding unicode as UTF-16
    if unicode_input:
        if encoding:
            xmlstr = xml.encode(encoding)
        else:
            xmlstr = xml.encode('UTF-8')
    else:
        xmlstr = xml
    if encoding:
        enc = encoding
    else:
        enc = sniff_bom_encoding(xmlstr)
    if unicode_input:
        xml = xmlstr
    # We must use an encoder to handle utf_8_sig properly.
    encode = codecs.lookup(enc).incrementalencoder().encode
    if bomless_utf16_re.match(enc):
        # These need a BOM prefix according to the spec but the default
        # Python encodings of that name don't provide one.
        prefix = encode(six.u('\ufeff'))
    else:
        prefix = encode('')
    chars_we_need = ('''abcdefghijklmnopqrstuvwxyz'''
                     '''ABCDEFGHIJKLMNOPQRSTUVWXYZ'''
                     '''0123456789.-_ \t\r\n<?'"[]:()+*>''')
    assert encode(chars_we_need * 3) == encode(chars_we_need) * 3, enc
    L = lambda s: re.escape(encode(s))  # encoded form of literal s
    group = lambda s: '(%s)' % s
    optional = lambda s: '(?:%s)?' % s
    oneof = lambda opts: '(?:%s)' % '|'.join(opts)
    charset = lambda s: oneof([L(c) for c in s])
    all_until = lambda s: '(?:(?!%s).)*' % s
    caseless = lambda s: oneof([L(c.lower()) for c in s] +
                               [L(c.upper()) for c in s])
    upper = charset('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    lower = charset('abcdefghijklmnopqrstuvwxyz')
    digits = charset('0123456789')
    punc = charset('._-')
    Name = '(?:%s%s*)' % (oneof([upper, lower]),
                          oneof([upper, lower, digits, punc]))
    Ss = charset(' \t\r\n\f') + '*'  # optional white space (inc. formfeed)
    Sp = charset(' \t\r\n\f') + '+'  # required white space (inc. formfeed)
    VERSION = encode('version')
    ENCODING = encode('encoding')
    STANDALONE = encode('standalone')
    StartDecl = ''.join([prefix, Ss, L('<'), Ss, L('?'), Ss,
                         oneof([L('xml'), L('xmL'), L('xMl'), L('xML'),
                                L('Xml'), L('XmL'), L('XMl'), L('XML')])])
    Attr = ''.join([group(Sp), group(Name), group(''.join([Ss, L('='), Ss])),
        oneof([
            group(L('"') + all_until(oneof([L('"'), L('<'), L('>')])) + L('"')),
            group(L("'") + all_until(oneof([L("'"), L('<'), L('>')])) + L("'")),
            group(all_until(oneof([Sp, L('?'), L('<'), L('>')]))),
        ])
    ])
    Attr_re = re.compile(Attr, re.DOTALL)
    EndDecl = ''.join([
        group(Ss), oneof([''.join([L('?'), Ss, L('>')]), L('>')])
    ])
    m = re.match(StartDecl, xml)
    if m:
        pos = m.end()
        attrs = {}
        while 1:
            m2 = Attr_re.match(xml, pos)
            if m2:
                wspace, name, eq, dquoted, squoted, unquoted = m2.groups()
                wspace = wspace.replace(encode('\f'), encode(' '))
                if dquoted is not None:
                    quotes = encode('"')
                    n = len(quotes)
                    value = dquoted[n:-n]
                elif squoted is not None:
                    quotes = encode("'")
                    n = len(quotes)
                    value = squoted[n:-n]
                else:
                    quotes = encode("'")  # works for cp1026 where '"' doesn't
                    value = unquoted
                if name in attrs:
                    pass  # TODO: warn: already got a value for xxx
                elif name == VERSION:
                    m3 = re.match(Ss + group(L("1.") + digits) + Ss + EOS,
                                  value)
                    if m3:
                        attrs[name] = wspace + name + eq + \
                                quotes + m3.group(1) + quotes
                    else:
                        pass  # TODO: warn: expected 1.x
                elif name == ENCODING:
                    m3 = re.match(Ss + group(Name) + Ss + EOS, value)
                    if m3:
                        attrs[name] = wspace + name + eq + \
                                quotes + m3.group(1) + quotes
                    else:
                        pass  # TODO: warn: expected a name
                elif name == STANDALONE:
                    m3 = re.match(
                        Ss + oneof([
                            group(oneof([
                                    L('yes'), L('yeS'), L('yEs'), L('yES'),
                                    L('Yes'), L('YeS'), L('YEs'), L('YES')])),
                            group(oneof([L('no'), L('nO'),
                                         L('No'), L('NO')]))
                        ]) + Ss + EOS,
                        value)
                    if m3:
                        yes, no = m3.groups()
                        if yes:
                            attrs[name] = wspace + name + eq + \
                                    quotes + encode('yes') + quotes
                        else:
                            attrs[name] = wspace + name + eq + \
                                    quotes + encode('no') + quotes
                    else:
                        pass  # TODO: warn: expected yes or no
                else:
                    pass  # TODO: warn: non-standard attribute name
                pos = m2.end()
            else:
                break  # doesn't look like an attribute, give up
        if add_encoding and ENCODING not in attrs:
            attrs[ENCODING] = encode(" encoding='%s'" % enc)
        m4 = re.compile(EndDecl).match(xml, pos)
        if m4:
            return (
                prefix + encode('<?xml') +
                attrs.get(VERSION, encode(" version='%s'" % default_version)) +
                (attrs.get(ENCODING) if ENCODING in attrs else '') +
                (attrs.get(STANDALONE) if STANDALONE in attrs else '') +
                m4.group(1).replace(encode('\f'), encode(' ')) +
                encode('?>') + xml[m4.end():])
        else:
            m5 = re.compile(oneof([L('>'), L('<')])).search(xml, pos)
            if m5:
                if m5.group() == encode('>'):
                    endpos = m5.end()
                else:
                    endpos = m5.start()
                return xml[:m.start()] + xml[endpos:]  # remove bad decl
            else:
                return ''  # unterminated, drop entire document (inc. BOM)
    if unicode_input:
        xml = xml.decode(enc, 'strict')  # reverse the encoding done earlier
    return xml  # no decl detected


def fix_doctype(html):
    """\
    Searches for a doctype declaration at the start of html, after any
    XML declaration and white-space, and makes sure its syntax matches
    the "doctypedecl" rule in the XML spec, with a few minor exceptions
    (we disallow '<' and '>' in PUBLIC identifiers, allow any
    combination of plausible characters for ELEMENT grammar rules,
    and disallow nested comments and processing instructions).
    Returns (fixed_doctype, index) where fixed_doctype is a fixed
    version of everything up to the end of the doctype and index is the
    position within html of the end of the doctype (so html[index:]
    can be processed including positions relative to the original input).
    """
    # This is a conversion of the grammar in the XML spec.
    # If you've never seen a description of what's allowed in the doctype,
    # try to read this code.  They were clearly bonkers.
    S = '[ \t\r\n]+'
    Ss = '[ \t\r\n]*'  # S?
    opt = lambda *args: '(?:%s)?' % '|'.join(args)
    oneof = lambda *args: '(?:%s)' % '|'.join(args)
    any = lambda *args: '(?:%s)*' % '|'.join(args)
    some = lambda *args: '(?:%s)+' % '|'.join(args)
    named = lambda name, regexp: '(?P<%s>%s)' % (name, regexp)
    NameStartChar = (
        six.u('[:A-Z_a-z\xC0-\xD6\xD8-\xF6\u00F8-\u02FF\u0370-\u037D') +
        six.u('\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF') +
        six.u('\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD]'))
    if len(six.u('\U00010000')) == 1:
        NameStartChar = NameStartChar[:-1] + six.u('\U00010000-\U000EFFFF]')
    NameChar = NameStartChar[:-1] + six.u("0-9\xB7\u0300-\u036F\u203F-\u2040\-]")
    Name = NameStartChar + any(NameChar)
    Nmtoken = some(NameChar)
    quoted = oneof('"[^<>"]*"', "'[^<>']*'")
    SystemLiteral = quoted  # XML spec allows < and > here, but that's silly.
    PubidLiteral = oneof('"[-\ \r\na-zA-Z0-9()+,./:=?;!*#@$_%\']*"',
                         "'[-\ \r\na-zA-Z0-9()+,./:=?;!*#@$_%]*'")
    ExternalID = oneof('SYSTEM' + S + SystemLiteral,
                       'PUBLIC' + S + quoted  # PubidLiteral
                                + S + SystemLiteral)
    Mixed = oneof(r'\(' + Ss + '#PCDATA' + any(Ss + r'\|' + Ss + Name)
                        + Ss + r'\)\*',
                  r'\(' + Ss + '#PCDATA' + Ss + r'\)')  # yuck.
    # Replacing this recursive grammar...
    #choice = r'\(' + Ss + cp + some(Ss + r'\|' + Ss + cp) + Ss + r'\)'
    #seq    = r'\(' + Ss + cp + any(Ss + r'\,' + Ss + cp) + Ss + r'\)'
    #cp = oneof(Name, choice, seq) + '[?*+]?'
    #children = oneof(choice, seq) + '[?*+]?'
    # with the simpler but more lenient line:
    children = some(Name, '[?*+|,()]', S)
    contentspec = oneof('EMPTY', 'ANY', Mixed, children)
    elementdecl = ('<!' + Ss + 'ELEMENT' + S + Name + S +
                   contentspec + Ss + '>')
    NotationType = ('NOTATION' + S + r'\(' + Ss + Name +
                    any(Ss + r'\|' + Ss + Name) + Ss + r'\)')
    Enumeration = (r'\(' + Ss + Nmtoken +
                   any(Ss + r'\|' + Ss + Nmtoken) + Ss + r'\)')
    AttType = oneof('CDATA', 'ID', 'IDREF', 'IDREFS',
                    'ENTITY', 'ENTITIES', 'NMTOKEN', 'NMTOKENS',
                    NotationType, Enumeration)
    CharRef = oneof('&#[0-9]+;', '&#x[0-9a-fA-F]+;')
    EntityRef = '&' + Name + ';'
    PEReference = '%' + Name + ';'
    Reference = oneof(EntityRef, CharRef)
    EntityValue = oneof('"' + any('[^%&"]', PEReference, Reference) + '"',
                        "'" + any("[^%&']", PEReference, Reference) + "'")
    AttValue = oneof('"' + any('[^<&"]', Reference) + '"',
                     "'" + any("[^<&']", Reference) + "'")
    DefaultDecl = oneof('#REQUIRED', '#IMPLIED', opt('#FIXED' + S) + AttValue)
    AttDef = S + Name + S + AttType + S + DefaultDecl
    AttlistDecl = '<!' + Ss + 'ATTLIST' + S + Name + any(AttDef) + Ss + '>'
    NDataDecl = S + 'NDATA' + S + Name
    EntityDef = oneof(EntityValue, ExternalID + opt(NDataDecl))
    PEDef = oneof(EntityValue, ExternalID)
    GEDecl = '<!' + Ss + 'ENTITY' + S + Name + S + EntityDef + Ss + '>'
    PEDecl = '<!' + Ss + 'ENTITY' + S + '%' + S + Name + S + PEDef + Ss + '>'
    EntityDecl = oneof(GEDecl, PEDecl)
    PublicID = 'PUBLIC' + S + quoted  # PubidLiteral
    NotationDecl = ('<!' + Ss + 'NOTATION' + S + Name + S +
                    oneof(ExternalID, PublicID) + Ss + '>')
    markupdecl = oneof(elementdecl, AttlistDecl, EntityDecl, NotationDecl,
                       #PI, Comment  -- disallowing these
                       )
    intSubset = any(markupdecl, PEReference, S)
    doctypedecl = (named('doctype', '<!' + Ss + 'DOCTYPE' + S + Name) +
                   named('body',
                       named('extid', opt(S + ExternalID) + Ss) +
                       named('subset', opt(r'\[' + intSubset + r'\]' + Ss)) +
                       '>'))
    doctypedecl = re.compile(doctypedecl + r'\Z', flags=re.IGNORECASE)

    def ERROR(message, charpos=None):
        if charpos is None:
            charpos = pos
        line = html.count('\n', 0, charpos) + 1
        offset = charpos - html.rfind('\n', 0, charpos)
        raise ValidationError(message, charpos, line, offset, [])

    # Start by looking for <! DOCTYPE ... >, possibly with <! ... >s inside.
    m = re.compile('<!' + Ss + 'DOCTYPE' + S + '[^<>]*' +
                   any('<![^<>]*>[^<>]*') + '>', re.IGNORECASE).search(html)
    if not m:
        return '', 0  # no <! DOCTYPE ... > found
    # Now check whether it's almost correct
    m2 = doctypedecl.match(html, m.start(), m.end())
    if not m2:
        raise ERROR('Invalid doctype', m.start())
    m = m2
    r = re.compile(S + 'PUBLIC' + S + '(%s)' % quoted, flags=re.IGNORECASE)
    for pubid in r.finditer(html, m.start(), m.end()):
        if not re.match(PubidLiteral + '\Z', pubid.group(1)):
            raise ERROR('Bad characters in PUBLIC "..." identifier',
                        pubid.start(1))

    # Now fix the few things about the doctype that we can fix
    def fix(m):
        g = m.group()
        if g[0] in '"\'':
            return g  # don't change anything in "..." or '...'
        elif g.startswith('<!'):
            return '<!'  # remove whitespace after <!
        else:
            return g.upper()  # convert keywords to uppercase
    before, doctype, body, after = (
        html[:m.start()], m.group('doctype'), m.group('body'), html[m.end():])
    doctype = re.sub(r'<!\s*(\S+)', lambda m: '<!' + m.group(1).upper(),
                     doctype)
    body = re.sub(oneof('"[^"]*"', "'[^']*'",
                        oneof('#', '!' + Ss) + '[a-zA-Z]+'),
                     fix, body)
    return before + doctype + body, m.end()


def xhtmlify(html, encoding=None,
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
    html = fix_xmldecl(html, encoding=encoding, add_encoding=False)
    if not encoding:
        encoding = sniff_encoding(html)
    unicode_input = isinstance(html, six.text_type)
    if unicode_input:
        html = html.encode(encoding, 'strict')
    if not isinstance(html, str):
        raise TypeError("Expected string, got %s" % type(html))
    html = html.decode(encoding, 'replace')
    # "in HTML, the Formfeed character (U+000C) is treated as white space"
    html = html.replace(six.u('\u000C'), six.u(' '))
    # Replace disallowed characters with U+FFFD (unicode replacement char)
    if len(six.u('\U00010000')) == 1:
        html = re.sub(  # XML 1.0 section 2.2, "Char" production
            six.u('[^\x09\x0A\x0D\u0020-\uD7FF\uE000-\uFFFD') +
              six.u('\U00010000-\U0010FFFF]'),  # <-- 32 bit characters
            six.u('\N{replacement character}'), html)
    else:
        # Replace 32-bit characters, this Python build doesn't support them
        html = re.sub(  # XML 1.0 section 2.2, "Char" production
            six.u('[^\x09\x0A\x0D\u0020-\uD7FF\uE000-\uFFFD]'),
            six.u('\N{replacement character}'), html)

    def ERROR(message, charpos=None):
        if charpos is None:
            charpos = pos
        line = html.count('\n', 0, charpos) + 1
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
    # Output the XML declaration and doctype, if they exist.
    doctype, lastpos = fix_doctype(html)
    output(doctype)
    if html.startswith('<?xml') or html.startswith(six.u('\ufeff<?xml')):
        pos = html.find('>') + 1
        if not doctype:
            output(html[:pos])
            lastpos = pos
    # Start processing tags
    tag_re = re.compile(TAG_RE, re.DOTALL | re.IGNORECASE)
    for tag_match in tag_re.finditer(html, lastpos):
        pos = tag_match.start()
        prevtag = tags and tags[-1][0].lower() or None
        innards = tag_match.group(1)
        if innards is None:
            whole_tag = tag_match.group()
            if whole_tag.startswith('<!'):
                # CDATA, comment, or doctype-alike. Treat as text.
                if re.match(r'(?i)<!doctype[ \t\r\n]', whole_tag):
                    text = html[lastpos:pos]
                    if re.match(r'[ \t\r\n]*\Z', text):
                        output(text)
                    output('<!DOCTYPE')
                    lastpos = tag_match.start() + len('<!doctype')
                continue
            assert whole_tag == '<'
            if prevtag in cdata_tags:
                continue  # ignore until we have all the text
            else:
                ERROR('Unescaped "<" or unfinished tag')
        elif not innards:
            ERROR("Empty tag")
        text = html[lastpos:pos]
        if prevtag in cdata_tags:
            m = re.match(r'/(%s)[ \t\r\n]*\Z' % NAME_RE, innards)
            if not m or m.group(1).lower() != prevtag:
                continue  # not the closing tag we need, keep treating as text
            output(cdatafix(text))
        else:
            output(ampfix(text))
        m = re.compile(INNARDS_RE, re.DOTALL).match(innards)
        if m.group(1):  # opening tag
            endslash = m.group(2)
            m = re.match(NAME_RE, innards)
            TagName, attrs = m.group(), innards[m.end():]
            tagname = TagName.lower()
            attrs = fix_attrs(tagname, attrs,
                ERROR=lambda msg, relpos:
                        ERROR(msg, tag_match.start(1) + m.end() + relpos))
            if prevtag in self_closing_tags:
                tags.pop()
                prevtag = tags and tags[-1][0].lower() or None
            # http://www.w3.org/TR/xhtml1/#prohibitions
            prohibitors_of = {
                'a': ['a'],
                'img': ['pre'], 'object': ['pre'], 'big': ['pre'],
                'small': ['pre'], 'sub': ['pre'], 'sup': ['pre'],
                'input': ['button'], 'select': ['button'],
                'textarea': ['button'],
                'button': ['button'], 'form': ['button', 'form'],
                'fieldset': ['button'], 'iframe': ['button'],
                'isindex': ['button'],
                'label': ['button', 'label'],
            }
            bad_parents = prohibitors_of.get(tagname, [])
            for ancestor, _ in tags:
                if ancestor in bad_parents:
                    if tagname == ancestor:
                        other_text = 'other '
                    else:
                        other_text = ''
                    ERROR("XHTML <%s> elements must not "
                          "contain %s<%s> elements" %
                          (ancestor, other_text, tagname))
            # I'm assuming only the tags listed below can self-nest,
            # and we automatically close <p> tags before structural tags.
            # HTML5 has many others like <section> that we don't support.
            if (tagname == prevtag and tagname not in ('div', 'span',
                    'fieldset', 'q', 'blockquote', 'ins', 'del', 'bdo',
                    'sub', 'sup', 'big', 'small')
               ) or (prevtag == 'p' and tagname in structural_tags):
                tags.pop()
                output('</%s>' % prevtag)
                #prevtag = tags and tags[-1][0].lower() or None  # not needed
            if endslash:
                output('<%s%s>' % (tagname, attrs))
            elif tagname in self_closing_tags:
                if attrs.rstrip() == attrs:
                    attrs += ' '
                output('<%s%s/>' % (tagname, attrs))  # preempt any closing tag
                tags.append((TagName, pos))
            else:
                output('<%s%s>' % (tagname, attrs))
                tags.append((TagName, pos))
        elif m.group(3):  # closing tag
            TagName = re.match(r'/(\w+)', innards).group(1)
            tagname = TagName.lower()
            if prevtag in self_closing_tags:
                # The tag has already been output in self-closed form.
                if prevtag == tagname:  # explicit close
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
            if prevtag != tagname and (
                 (prevtag == 'p' and tagname in structural_tags) or
                 (prevtag == 'li' and tagname in ('ol', 'ul')) or
                 (prevtag == 'dd' and tagname == 'dl') or
                 (prevtag == 'area' and tagname == 'map') or
                 (prevtag == 'td' and tagname == 'tr') or
                 (prevtag == 'th' and tagname == 'tr')
            ):
                output('</%s>' % prevtag)
                tags.pop()
                prevtag = tags and tags[-1][0].lower() or None
            if prevtag == tagname:
                if tagname not in self_closing_tags:
                    output(tag_match.group().lower())
                    tags.pop()
            else:
                ERROR("Unexpected closing tag </%s>" % TagName)
        elif m.group(4):  # mismatch
            ERROR("Malformed tag")
        else:
            # We don't do any validation on pre-processing tags (<? ... >).
            output(ampfix(tag_match.group()))
        lastpos = tag_match.end()
    prevtag = tags and tags[-1][0].lower() or None
    if prevtag in cdata_tags:
        output(cdatafix(html[lastpos:]))
    else:
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
        if len(sys.argv) == 2:
            if sys.argv[1] == '-':
                html = sys.stdin.read()
            else:
                html = open(sys.argv[1]).read()
        else:
            sys.exit('usage: %s HTMLFILE' % sys.argv[0])
    xhtml = xhtmlify(html)
    try:
        assert xhtml == xhtmlify(xhtml)
    except ValidationError:
        print(xhtml)
        raise
    xmlparse(re.sub('(?s)<!(?!\[).*?>', '', xhtml))  # ET can't handle <!...>
    if len(sys.argv) == 2:
        sys.stdout.write(xhtml)
    return xhtml


def xmlparse(snippet, encoding=None, wrap=None):
    """Parse snippet as XML with ElementTree/expat.  By default it wraps the
       snippet in an outer <document> element before parsing (unless the
       snippet starts "<?xml" or u"\ufeff<?xml").  This can be suppressed by
       setting wrap to True or forced by setting wrap to False."""
    import xml.parsers.expat
    from xml.etree import ElementTree as ET
    if wrap is None:
        wrap = (not snippet.startswith('<?xml') and
                not snippet.startswith(six.u('\ufeff<?xml')))
    try:
        if encoding:
            try:
                parser = ET.XMLParser(encoding=encoding)
            except TypeError:
                parser = ET.XMLParser()  # old version
        else:
            parser = ET.XMLParser()  # let it use the standard algorithm
        if wrap:  # XXX: not safe for non-ascii-ish encoded strs
            input = '<document>\n%s\n</document>' % snippet
        else:
            input = snippet
        if isinstance(snippet, six.text_type):
            if not encoding:
                encoding = sniff_encoding(snippet)
            input = input.encode(encoding)
        parser.feed(input)
        parser.close()
    except xml.parsers.expat.ExpatError as e:
        lineno, offset = e.lineno, e.offset
        lineno -= 1
        if lineno == input.count('\n'):  # last line => </document>
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
    if isinstance(xml, six.binary_type):
        xmlstr = xml
    elif isinstance(xml, six.text_type):
        xmlstr = xml.encode('utf-8')
    else:
        raise TypeError('Expected a string, got %r' % type(xml))
    enc = sniff_bom_encoding(xmlstr)
    # Now the fun really starts. We compile the encoded sniffer regexp.
    # We must use an encoder to handle utf_8_sig properly.
    encode = codecs.lookup(enc).incrementalencoder().encode
    prefix = encode('')  # any header such as a UTF-8 BOM
    if enc in ('utf_16_le', 'utf_16_be'):
        prefix = six.u('\ufeff').encode(enc)  # the standard approach fails
    L = lambda s: re.escape(encode(s))  # encoded form of literal s
    optional = lambda s: '(?:%s)?' % s
    oneof = lambda opts: '(?:%s)' % '|'.join(opts)
    charset = lambda s: oneof([L(c) for c in s])
    upper = charset('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    lower = charset('abcdefghijklmnopqrstuvwxyz')
    digit = charset('0123456789')
    digits = digit + '+'
    punc = charset('._-')
    name = '(?:%s%s*)' % (oneof([upper, lower]),
                          oneof([upper, lower, digit, punc]))
    Ss = charset(' \t\r\n') + '*'  # optional white space
    Sp = charset(' \t\r\n') + '+'  # required white space
    Eq = ''.join([Ss, L('='), Ss])
    VersionInfo = ''.join([
        Sp,
        L('version'),
        Eq,
        oneof([
            L("'1.") + digits + L("'"),
            L('"1.') + digits + L('"'),
        ])
    ])
    EncodingDecl = ''.join([
        Sp,
        L('encoding'),
        Eq,
        oneof([
            L("'") + '(?P<enc_dq>%s)' % name + L("'"),
            L('"') + '(?P<enc_sq>%s)' % name + L('"')
        ])
    ])
    # standalone="yes" is valid XML but almost certainly a lie...
    SDDecl = ''.join([
        Sp,
        L('standalone'),
        Eq,
        oneof([
            L("'") + oneof([L('yes'), L('no')]) + L("'"),
            L('"') + oneof([L('yes'), L('no')]) + L('"'),
        ])
    ])
    R = ''.join([
        prefix,
        L('<?xml'),
        VersionInfo,
        optional(EncodingDecl),
        optional(SDDecl),
        Ss,
        L('?>')
    ])
    m = re.match(R, xml)
    if m:
        encvalue = m.group('enc_dq')
        if encvalue is None:
            encvalue = m.group('enc_sq')
            if encvalue is None:
                return enc
        decl_enc = encvalue.decode(enc).encode('ascii')
        bom_codec = None

        def get_codec(encoding):
            encoding = encoding.lower()
            if encoding == 'ebcdic':
                encoding = 'cp037'  # good enough
            elif encoding in ('utf_16_le', 'utf_16_be'):
                encoding = 'utf_16'
            return codecs.lookup(encoding)
        try:
            bom_codec = get_codec(enc)
        except LookupError:
            pass  # unknown BOM codec, old version of Python maybe?
        try:
            if (bom_codec and enc == enc.lower() and
                get_codec(decl_enc) != bom_codec):
                    raise ValidationError(
                        "Multiply-specified encoding "
                        "(BOM: %s, XML decl: %s)" % (enc, decl_enc),
                        0, 1, 1, [])
        except LookupError:
            pass  # unknown encoding specified, let it pass
        return decl_enc
    else:
        return 'UTF-8'


def sniff_bom_encoding(xml):
    """Reads any byte-order marker. Returns the implied encoding.
       If the returned encoding is lowercase it means the BOM uniquely
       identified an encoding, so we don't need to parse the <?xml...?>
       to extract the encoding in theory."""
    if not isinstance(xml, six.binary_type):
        raise TypeError('Expected str/bytes, got %r' % type(xml))
    # Warning: The UTF-32 codecs aren't present before Python 2.6...
    # See also http://bugs.python.org/issue1399
    enc = {
        '\x00\x00\xFE\xFF': 'utf_32',  # UCS4 1234, utf_32_be with BOM
        '\xFF\xFE\x00\x00': 'utf_32',  # UCS4 4321, utf_32_le with BOM
        '\x00\x00\xFF\xFE': 'undefined',  # UCS4 2143 (rare, we give up)
        '\xFE\xFF\x00\x00': 'undefined',  # UCS4 3412 (rare, we give up)
        '\x00\x00\x00\x3C': 'UTF_32_BE',  # UCS4 1234 (no BOM)
        '\x3C\x00\x00\x00': 'UTF_32_LE',  # UCS4 4321 (no BOM)
        '\x00\x00\x3C\x00': 'undefined',  # UCS4 2143 (no BOM, we give up)
        '\x00\x3C\x00\x00': 'undefined',  # UCS4 3412 (no BOM, we give up)
        '\x00\x3C\x00\x3F': 'UTF_16_BE',  # missing BOM
        '\x3C\x00\x3F\x00': 'UTF_16_LE',  # missing BOM
        '\x3C\x3F\x78\x6D': 'ASCII',
        '\x4C\x6F\xA7\x94': 'CP037',  # EBCDIC (unknown code page)
    }.get(xml[:4])
    if enc and enc == enc.lower():
        return enc
    if not enc:
        if xml[:3] == '\xEF\xBB\xBF':
            return 'utf_8_sig'  # UTF-8 with these three bytes prefixed
        elif xml[:2] == '\xFF\xFE':
            return 'utf_16_le'
        elif xml[:2] == '\xFE\xFF':
            return 'utf_16_be'
        else:
            enc = 'UTF-8'  # "Other"
    return enc

if __name__ == '__main__':
    test()
