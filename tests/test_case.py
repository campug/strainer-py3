from __future__ import print_function
from strainer.case import call_super, STestCase, DelayedException
from strainer.xhtmlify import PY3
from nose.tools import eq_, raises


class FooTest(STestCase):
    def setUp(self):
        STestCase.setUp(self)
        self.capture_stdout()

    def _call(self, name):
        print(name if PY3 else name.decode())

    def foo(self):
        """There is no superclass here"""
        self._call('foo0')

    @call_super(after=True, delay=False)
    def broke_foo(self):
        self._call('broke_foo')

    def broke_bar(self):
        self._call('broke_bar0')
        raise Exception('bar exception')

    def bar(self):
        self._call('bar0')

    def skip_gen(self):
        self._call('skip0')

class FooChildTest(FooTest):
    @call_super(before=True, delay=False)
    def foo(self):
        self._call('foo1')

    @call_super(after=True, delay=False)
    def bar(self):
        self._call('bar1')

    @call_super(after=True, delay=True)
    def broke_bar(self):
        self._call('broke_bar1')

class TestChildsChild(FooChildTest):
    @call_super(before=True, delay=False)
    def foo(self):
        self._call('foo2')

    @call_super(after=True, delay=False)
    def bar(self):
        self._call('bar2')

    @call_super(after=True, delay=False)
    def skip_gen(self):
        self._call('skip2')

    @raises(AttributeError)
    def testBrokeFoo(self):
        self.broke_foo()

    def testBrokeBar(self):
        try:
            self.broke_bar()
        except DelayedException as e:
            eq_(self.output.getvalue(), 'broke_bar1\nbroke_bar0\n')
        else:
            self.fail('broke_bar should have raised a DelayedException')

    def testFoo(self):
        self.foo()
        eq_(self.output.getvalue(), "foo0\nfoo1\nfoo2\n")

    def testBar(self):
        self.bar()
        eq_(self.output.getvalue(), 'bar2\nbar1\nbar0\n')

    def testSkipGen(self):
        self.skip_gen()
        eq_(self.output.getvalue(), 'skip2\nskip0\n')

