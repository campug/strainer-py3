from xhtmlify import xhtmlify, ValidationError
from xml.etree import ElementTree as etree
from xml.parsers.expat import ExpatError
import copy, re

def remove_whitespace_nodes(node):
    new_node = copy.copy(node)
    new_node._children = []
    if new_node.text and new_node.text.strip() == '':
        new_node.text = ''
    if new_node.tail and new_node.tail.strip() == '':
        new_node.tail = ''
    for child in node.getchildren():
        if child is not None:
            child = remove_whitespace_nodes(child)
        new_node.append(child)
    return new_node

def remove_namespace(doc):
    """Remove namespace in the passed document in place."""
    for elem in doc.getiterator():
        match = re.match('(\{.*\})(.*)', elem.tag)
        if match:
            elem.tag = match.group(2)

def normalize_to_xhtml(needle):
# i dont think this is needed any more... more testing required (xmlify does it)
#    needle = replace_escape_chars(needle)
    #first, we need to make sure the needle is valid html
    needle = xhtmlify(needle)
    try:
        needle_node = etree.fromstring(needle)
    except ExpatError, e:
        raise ExpatError('Could not parse %s into xml. %s'%(needle, e.args[0]))
    needle_node = remove_whitespace_nodes(needle_node)
    remove_namespace(needle_node)
    needle_s = etree.tostring(needle_node)
    return needle_s

def in_xhtml(needle, haystack):
    try:
        needle_s = normalize_to_xhtml(needle)
    except ValidationError:
        raise ValidationError('Could not parse needle: %s into xml.'%needle)
    try:
        haystack_s = normalize_to_xhtml(haystack)
    except ValidationError:
        raise ValidationError('Could not parse haystack: %s into xml.'%haystack)
    return needle_s in haystack_s

def eq_xhtml(needle, haystack):
    try:
        needle_s = normalize_to_xhtml(needle)
    except ValidationError, e:
        raise ValidationError('Could not parse needle: %s into xml. %s'%(needle, e.message))
    try:
        haystack_s = normalize_to_xhtml(haystack)
    except ValidationError, e:
        raise ValidationError('Could not parse haystack: %s into xml. %s'%(haystack, e.message))
    return needle_s == haystack_s

def assert_in_xhtml(needle, haystack):
    """
    assert that one xhtml stream can be found within another
    """
    assert in_xml(needle, haystack), "%s not found in %s"%(needle, haystack)

def assert_eq_xhtml(needle, haystack):
    """
    assert that one xhtml stream equals another
    """
    assert eq_xml(needle, haystack), "%s \n --- does not equal ---\n%s"%(needle, haystack)
