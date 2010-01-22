from xhtmlify import xhtmlify, ValidationError
from xml.etree import ElementTree as etree
from xml.parsers.expat import ExpatError
import copy, re
from pprint import pformat, pprint
from simplejson import loads
from nose.tools import *

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
    except ValidationError, e:
        raise ValidationError('Could not parse needle: %s into xml. %s'%(needle, e.message))
    try:
        haystack_s = normalize_to_xhtml(haystack)
    except ValidationError, e:
        print e.message
        raise ValidationError('Could not parse haystack: %s into xml. %s'%(haystack, e.message))
    return needle_s in haystack_s

def eq_xhtml(needle, haystack):
    try:
        needle_s = normalize_to_xhtml(needle)
    except ValidationError, e:
        raise ValidationError('Could not parse needle: %s into xml. %s'%(needle, e.message))
    try:
        haystack_s = normalize_to_xhtml(haystack)
    except ValidationError, e:
        print e.message
        raise ValidationError('Could not parse haystack: %s into xml. %s'%(haystack, e.message))
    return needle_s == haystack_s

def assert_in_xhtml(needle, haystack):
    """
    assert that one xhtml stream can be found within another
    """
    assert in_xhtml(needle, haystack), "%s not found in %s"%(needle, haystack)

def assert_eq_xhtml(needle, haystack):
    """
    assert that one xhtml stream equals another
    """
    assert eq_xml(needle, haystack), "%s \n --- does not equal ---\n%s"%(needle, haystack)

def assert_raises(exc, method, *args, **kw):
    try:
        method(*args, **kw)
    except exc, e:
        return e
    else:
        raise AssertionError('%s() did not raise %s' % (method.__name__, exc.__name__))

def num_eq(one, two):
    assert type(one)==type(two), 'The types %s and %s do not match' % (type(one), type(two))
    eq_(one, two, 'The values %s and %s do not equal' % (one, two))

def neq_(one, two, msg = None):
    """Shorthand for 'assert a != b, "%r == %r" % (a, b)
    """
    assert a != b, msg or "%r == %r" % (a, b)

def eq_pprint(a, b, msg=None):
    if a != b:
        pprint(a)
        print 'does not equal'
        pprint(b)
    assert a == b, msg or "%r != %r" % (a, b)

def _eq_list(ca, cb, ignore=None):
    eq_pprint(len(ca), len(cb), "the lengths of the lists are different %s != %s" % (str(ca), str(cb)))
    for i, v in enumerate(ca):
        if isinstance(v, dict):
            _eq_dict(ca[i], cb[i], ignore=ignore)
        elif isinstance(v, list):
            _eq_list(ca[i], cb[i], ignore=ignore)
        else:
            eq_pprint(ca[i], cb[i])

def _eq_dict(ca, cb, ignore=None):
    # assume ca and cb can be destructively modified
    if ignore:
        for key in ignore:
            if key in ca:
                del ca[key]
            if key in cb:
                del cb[key]

    #this needs to be recursive so we can '&ignore'-out ids anywhere in a json stream
    for key in set(ca.keys() + cb.keys()):
        assert key in ca, '%s!= %s\n key "%s" not in first argument' %(ca, cb, key)
        assert key in cb, '%s!= %s\n key "%s" not in second argument' %(ca, cb, key)
        v1 = ca[key]
        v2 = cb[key]
        if v1 == '&ignore' or v2 == '&ignore':
            continue
        if not isinstance(v2, basestring) and isinstance(v1, basestring):
            eq_pprint(type(v1), type(v2), 'The types of values for "%s" do not match' % key)
        if isinstance(v1, list):
            _eq_list(v1, v2, ignore=ignore)
        elif isinstance(v1, dict):
            _eq_dict(v1, v2, ignore=ignore)
        else:
            eq_pprint(v1, v2, 'value of key "%s" does not equal:\n%s\ninstead, it\'s:\n%s'%(key, ca[key], cb[key]))
    #By this point, we've already checked all the keys and values, so don't compare again
 

def eq_dict(a, b, ignore=None):
    #Make a copy as our search for ignored values is destructive
    ca = copy.deepcopy(a)
    cb = copy.deepcopy(b)
                
    _eq_dict(ca, cb, ignore=ignore)

def eq_json(a, b):
    if isinstance(a, basestring):
        a = loads(a)
    if isinstance(b, basestring):
        b = loads(b)
        
    eq_dict(a, b)


__all__ = [_key for _key in locals().keys() if not _key.startswith('_')]

