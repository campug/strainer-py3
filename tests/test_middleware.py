import logging
from strainer.middleware import XHTMLifyMiddleware
from strainer.middleware import WellformednessCheckerMiddleware
try:
    from strainer.middleware import XHTMLValidatorMiddleware
except ImportError:
    XHTMLValidatorMiddleware = None

from strainer.doctypes import DOCTYPE_XHTML1_STRICT


# Mocks and other test detritus

class FakeWSGIApp(object):
    def __init__(self, response,
                 status='200 OK', headers=[('Content-type','text/html')]):
        self.response = response
        self.status = status
        self.headers = headers

    def __call__(self, environ, start_response):
        start_response(self.status, self.headers)
        return [self.response]


def fake_start_response(status, headers, exc_info=None):
    pass

class LogCaptureHandler(logging.Handler):
    """Appends record.getMessage() to a list for each record logged."""
    def __init__(self, list):
        logging.Handler.__init__(self)
        self.list = list
    def emit(self, record):
        self.list.append(record.getMessage())


def test_xhtml_validator_middleware():
    """This test is expected to fail if lxml isn't available."""
    STRICT = DOCTYPE_XHTML1_STRICT
    tests = [
        ('<html>\n<body>\nHello World!\n</body>\n</html>',
         ['Validation failed: no DTD found !, line 1, column 6']),

        ('<!doctype><html>\n<body>\nHello World!\n</body>\n</html>',
         ['StartTag: invalid element name, line 1, column 2']),

        ('<!DOCTYPE><html>\n<body>\nHello World!\n</body>\n</html>',
         ['xmlParseDocTypeDecl : no DOCTYPE name !, line 1, column 10']),

        (STRICT + '<html>\n<body>\nHello World!\n</body>\n</html>',
         ['Element body content does not follow the DTD, expecting '
          '(p | h1 | h2 | h3 | h4 | h5 | h6 | div | ul | ol | dl | pre | '
          'hr | blockquote | address | fieldset | table | form | noscript '
          '| ins | del | script)*, got (CDATA), line 5, column 3']),

        (STRICT + '<html><head><title></title></head><body></body></html>',
         []),
    ]
    for r, e in tests:
        errors = []
        app = XHTMLValidatorMiddleware(FakeWSGIApp(r),
                                       record_error=errors.append)
        response = app({}, fake_start_response)
        assert response==[r]
        assert errors==e

def test_xhtml_validator_middleware_logging():
    """This test is expected to fail if lxml isn't available."""
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = XHTMLValidatorMiddleware(FakeWSGIApp('<html>'))
    response = app({}, fake_start_response)
    assert response==['<html>'], repr(response)
    assert errors==['Validation failed: no DTD found !, line 1, column 6']

def test_xhtmlify_middleware_runs():
    app = XHTMLifyMiddleware(FakeWSGIApp('<html>'))
    response = app({}, fake_start_response)
    assert response==['<html xmlns="http://www.w3.org/1999/xhtml"></html>']

def test_xhtmlify_middleware_output_is_validatable():
    """This test is expected to fail if lxml isn't available."""
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = XHTMLifyMiddleware(FakeWSGIApp('<html>'))
    app2 = XHTMLValidatorMiddleware(app, doctype=DOCTYPE_XHTML1_STRICT)
    response = app2({}, fake_start_response)
    assert response==['<html xmlns="http://www.w3.org/1999/xhtml"></html>']
    assert errors==['Element html content does not follow the DTD, '
                    'expecting (head , body), got , line 1, column 15']

def test_xhtmlify_middleware_output_is_wellformed():
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = XHTMLifyMiddleware(FakeWSGIApp('<html>'))
    app = WellformednessCheckerMiddleware(app)
    response = app({}, fake_start_response)
    assert response==['<html xmlns="http://www.w3.org/1999/xhtml"></html>']
    assert errors==[]

def test_wellformedness_checker_runs():
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = FakeWSGIApp('<html><body></html>')
    app = WellformednessCheckerMiddleware(app)
    response = app({}, fake_start_response)
    assert response==['<html><body></html>']
    assert errors==['line 1, column 15: mismatched tag']

def test_wellformedness_checker_detects_unknown_entities():
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = FakeWSGIApp('<html>\n&lt;&euro;&snort;</html>')
    app = WellformednessCheckerMiddleware(app)
    response = app({}, fake_start_response)
    assert response==['<html>\n&lt;&euro;&snort;</html>']
    assert errors==['line 2, column 11: undefined entity']

def test_wellformedness_checker_detects_unknown_entities():
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = FakeWSGIApp('<html>\n&lt;&euro;&snort;</html>')
    app = WellformednessCheckerMiddleware(app)
    response = app({}, fake_start_response)
    assert response==['<html>\n&lt;&euro;&snort;</html>']
    assert errors==['line 2, column 11: undefined entity']

def test_wellformedness_checker_detects_xhtml_entities_in_xml():
    log = logging.getLogger('strainer.middleware')
    errors = []
    log.addHandler(LogCaptureHandler(errors))
    app = FakeWSGIApp('<html>\n&lt;&euro;</html>',
                      headers=[('Content-Type', 'application/xml')])
    app = WellformednessCheckerMiddleware(app)
    response = app({}, fake_start_response)
    assert response==['<html>\n&lt;&euro;</html>']
    assert errors==['line 2, column 5: undefined entity']
