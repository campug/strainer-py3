"""Provides WSGI middleware for validating and tidying HTML output."""
import re
import xhtmlify
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


__all__ = ['XHTMLValidatorMiddleware', 'XHTMLifyMiddleware',
           'WellformednessCheckerMiddleware', 'JSONValidatorMiddleware']


LOG = logging.getLogger('strainer.middleware')

def get_content_type(headers, default=''):
    """Returns the value of the content-type header or default."""
    for key, value in headers:
        if key.lower()=='content-type':
            return value
    return default

class BufferingMiddleware(object):
    """Buffers the response and passes it through self.filter()."""
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        output = StringIO()
        start_response_args = []
        def dummy_start_response(status, headers, exc_info=None):
            start_response_args.append((status, headers, exc_info))
            return output.write
        app_iter = self.app(environ, dummy_start_response)
        for line in app_iter:
            output.write(line)
        if hasattr(app_iter, 'close'):
            app_iter.close()
        response = output.getvalue()
        output.close()
        status, headers, exc_info = start_response_args[-1]
        filtered_response = self.filter(status, headers, exc_info, response)
        start_response(*start_response_args[-1])
        return [filtered_response]

    def filter(self, status, headers, exc_info, response):
        """Returns some response string which may differ from that passed in.
           response should be a string in both input and output."""
        return response

try:
    from validate import validate_xhtml, XHTMLSyntaxError

    class XHTMLValidatorMiddleware(BufferingMiddleware):
        def __init__(self, app, doctype='', record_error=LOG.error):
            """The middleware will output XHTML validation error messages
               by calling record_error(message)."""
            super(XHTMLValidatorMiddleware, self).__init__(app)
            self.doctype = doctype
            self.record_error = record_error

        def filter(self, status, headers, exc_info, response):
            content_type = get_content_type(headers)
            content_type = content_type.split(';')[0].strip()
            if content_type in ('text/html', 'application/xml+html'):
                try:
                    validate_xhtml(response, doctype=self.doctype)
                except XHTMLSyntaxError, e:
                    self.record_error(str(e))
            return response
except ImportError:
    pass  # no lxml, no XHTMLValidatorMiddleware, sorry.


class XHTMLifyMiddleware(BufferingMiddleware):
    def filter(self, status, headers, exc_info, response):
        content_type = get_content_type(headers)
        parts = content_type.split(';', 1)
        if len(parts)==2:
            content_type, rest = parts
        else:
            rest = ''
        encoding = re.search(
            r"""charset\s*=\s*("[A-Za-z0-9_-]*"|"""
                           r"""'[A-Za-z0-9_-]*'|"""
                           r"""[A-Za-z0-9_-]*)""", rest)
        if encoding:
            encoding = encoding.group(1).replace('"', '').replace("'", '')
        if content_type.strip() in ('text/html', 'application/xml+html'):
            response = xhtmlify.xhtmlify(response, encoding=encoding)
        return response


from wellformed import is_wellformed_xhtml, is_wellformed_xml

class WellformednessCheckerMiddleware(BufferingMiddleware):
    """Checks that served webpages are well-formed HTML/XHTML/XML,
       according to the Content-Type header.

       This is mainly just a check for correct entities, tag structure and
       nesting, no DTD checking is done.  Failures are logged by calling the
       record_error which was passed to the constructor.  By default this
       logs to the "strainer.middleware" channel using the standard logging
       module.
    """
    def __init__(self, app, record_error=LOG.error):
        """The middleware will output HTML/XHTML/XML wellformedness
           error messages by calling record_error(message)."""
        super(WellformednessCheckerMiddleware, self).__init__(app)
        self.record_error = record_error

    def filter(self, status, headers, exc_info, response):
        content_type = get_content_type(headers)
        content_type = content_type.split(';')[0].strip()
        if content_type in ('text/html', 'application/xml+html'):
            is_wellformed_xhtml(response, record_error=self.record_error)
        elif content_type.split('+')[0]=='application/xml':
            is_wellformed_xml(response, record_error=self.record_error)
        return response

from validate import validate_json, JSONSyntaxError

class JSONValidatorMiddleware(BufferingMiddleware):
    def __init__(self, app, doctype='', record_error=LOG.error):
        """The middleware will output JSON validation error messages
           by calling record_error(message)."""
        super(JSONValidatorMiddleware, self).__init__(app)
        self.record_error = record_error

    def filter(self, status, headers, exc_info, response):
        content_type = get_content_type(headers)
        content_type = content_type.split(';')[0].strip()
        if content_type=='text/json':
            try:
                validate_json(response)
            except JSONSyntaxError, e:
                self.record_error(str(e))
        return response
