import logging
try:
    from strainer.middleware import XHTMLValidatorMiddleware
except ImportError:
    XHTMLValidatorMiddleware = None

from strainer.doctypes import DOCTYPE_XHTML1_STRICT


# Mocks and other test detritus

class FakeWSGIApp(object):
    def __init__(self, response):
        self.response = response
    def __call__(self, environ, start_response):
        start_response('200 OK',[('Content-type','text/html')])
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

