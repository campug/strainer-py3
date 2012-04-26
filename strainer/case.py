import sys
from cStringIO import StringIO

import inspect
import traceback
import logging
log = logging.getLogger(__name__)

import unittest

__all__ = [
    'STestCase',
    'call_super',
    'DelayedException',
    'exception_raiser_generator',
    'exc_raiser_gen',
    'erg',
]


class STestCase(unittest.TestCase):
    '''
    Provides some fun stuff, like quick and easy attribute replacement and
    automatic cleanup
    '''
    def capture_stdout(self):
        '''Captures stdout to self.output until the tearDown routine is run'''
        self.output = StringIO()
        self.mock(sys, 'stdout', self.output)

    def mock(self, obj, attr_name, repl):
        self.__mocked.append((obj, attr_name, getattr(obj, attr_name)))
        setattr(obj, attr_name, repl)

    __mocked = []

    def setUp(self):
        self.__mocked = list()

    def tearDown(self):
        for obj, attr_name, orig in reversed(self.__mocked):
            setattr(obj, attr_name, orig)


class DelayedException(Exception):
    """Delayed Exception"""
    def __str__(self):
        return self.__class__.__doc__ + ": " + \
                ', '.join([str(e) for e in self.args])

#Default delay action is to not delay
delay = False


def call_super(after=None, before=None, delay=delay):
    """
    Call the super class's method of the same name either before or after
    calling the decorated class.  The call gets made regardless of the outcome
    of the decorated method, so it is suitable for calling teardown safely.

    If before and after are both set, the value for "after" will take
    precedence.

    This method can handle recursive calls up the tree.  It uses C{super} to
    determine the baseclass method to call, so your class structure must
    support that.
    """
    # we trigger on after, so set after based on before if after is not set
    if after is None and before:
        after = False

    def dec_call_super(func):
        """
        Always call the superclass's matching method, regardless of the outcome
        of the child class's method.
        """
        def wrapped_call_super(self, klass=None):
            delayed = []

            def append_delayed_and_print_traceback(e):
                # With the caught exception, log it, and delay it
                delayed.append(e)
                log.debug(traceback.format_exc(sys.exc_info()[2]))
                log.error(str(e))

            def get_and_call_super(klass):
                # Calls the super class function, catching, logging and
                # delaying any exceptions that might occur
                try:
                    if not klass:
                        klass = self.__class__
                    # skip generations that don't define a method
                    # named func.__name__
                    for cls in inspect.getmro(klass):
                        if func.__name__ in cls.__dict__:
                            klass = cls
                            break
                    else:
                        raise AttributeError('%s not found on %s' % (
                            func.__name__, func.im_class.__name__))
                    superfunc = getattr(super(klass, self), func.__name__)
                    #superfunc is bound, so "self" is implied
                    #Args and KW needed?
                    if superfunc.__name__ == wrapped_call_super.__name__:
                        #For recursion up the base trunk
                        superfunc(klass.__base__)
                    else:
                        superfunc()
                except Exception, e:
                    if delay:
                        append_delayed_and_print_traceback(e)
                    else:
                        raise
            #Before
            if not after:
                get_and_call_super(klass)
            #During
            try:
                ret = func(self)
            except Exception, e:
                if delay:
                    append_delayed_and_print_traceback(e)
                else:
                    raise
            #After
            if after:
                get_and_call_super(klass)
            # Cleanup
            if delayed:
                raise DelayedException(*delayed)
            return ret
        wrapped_call_super.__wrapped_func__ = func
        return wrapped_call_super
    dec_call_super.args = (after,)
    return dec_call_super


def assert_raises(exc, method, *args, **kwargs):
    '''Like the nose tool of the same name, but returns the exception
    raised so that args can be checked'''
    try:
        ret = method(*args, **kwargs)
    except exc, e:
        return e
    else:
        raise AssertionError(
            'The expected exception (%s) was not raised' % exc.__name__)


def exception_raiser_generator(exc, *args, **kwargs):
    '''
    Creates a method, suitable for using with C{STestCase.mock}, that raises
    the specified exception, with the supplied arguments.
    @param exc: Exception class to raise
    @type exc: A class descended from Exception, or other raiseable error
    @returns: A method that when called with any arguments raises the
              specified exception
    @rtype: method
    '''
    def raiser(*a, **kw):
        raise exc(*args, **kwargs)
    return raiser

exc_raiser_gen = erg = exception_raiser_generator
