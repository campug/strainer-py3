from setuptools import setup, find_packages
import sys, os

version = '0.1.1'

setup(name='strainer',
      version=version,
      description="Tools to allow developers to cleanup web serialization objects (HTML, JSON, XHTML)",
      long_description="""\
Provides middleware for detecting and correcting errors in web pages that are
served via the standard WSGI protocol used by most Python web frameworks.
By default, validation errors are logged to the "strainer.middleware" channel
using the standard Python logging module.

You should read the documentation for your web framework to find out how to
get the "WSGI application" that is responsible for serving your web site.
In Pylons, for example, the following code could be added in the
``config/middleware.py`` file.

To add HTML/XHTML/XML well-formedness validation to your WSGI app::

    >>> from strainer.middleware import WellformednessCheckerMiddleware
    >>> app = WellformednessCheckerMiddleware(app)

This uses the expat parser to detect most syntax errors and mismatched tags, 
but it won't perform stricter checks that the document structure matches the 
XHTML DTD, such as detecting disallowed child tags or attributes.  For that 
you should install a recent version of lxml (e.g. "easy_install lxml") and 
use XHTMLValidatorMiddleware instead, with code such as::

    >>> from strainer.middleware import XHTMLValidatorMiddleware
    >>> app = XHTMLValidatorMiddleware(app)

To add JSON validation to your WSGI app::

    >>> from strainer.middleware import JSONValidatorMiddleware
    >>> app = JSONValidatorMiddleware(app)

If your web framework doesn't provide an alternative handler for the error 
messages that are logged to the "strainer.middleware" channel, you can have 
them printed to sys.stderr with::

    >>> import logging
    >>> logging.basicConfig()

To add automatic correction of common HTML and XHTML errors to your WSGI app::

    >>> from strainer.middleware import XHTMLifyMiddleware
    >>> app = XHTMLifyMiddleware(app)

This is somewhat experimental, but it will improve faster if people use it 
and email us bug reports...

As with all (or at least most) WSGI middleware, you can also combine them::

    >>> app = XHTMLifyMiddleware(app)
    >>> app = XHTMLValidatorMiddleware(app)
    >>> app = JSONValidatorMiddleware(app)

The middleware in this package buffer the output internally (this violates
the PEP 333 specification, but it seems unavoidable), so it is best to use 
them near the top of the middleware stack.
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='html xhtml json wsgi',
      author='Tom Lynn and Chris Perkins',
      author_email='chris@percious.com',
      url='',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      package_data={'strainer': ['dtds/*']},
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
