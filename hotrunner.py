import re
import time
from xml.etree import ElementTree as ET

from django.conf import settings
from django.test.simple import DjangoTestSuiteRunner

# use django's bundled copy of unittest2 if necessary
from django.utils.unittest import TextTestResult, TextTestRunner

__all__ = ['HotRunner']
__version__ = '0.2.2'


class HotRunner(DjangoTestSuiteRunner):

    """This rolls in functionality from several other test runners,
    to make tests slightly awesomer.  In particular:
    
    * Apps can be excluded from the test runner by adding them
      to ``settings.EXCLUDED_TEST_APPS``.  To run all tests in spite
      of this setting, set ``TEST_ALL_APPS`` to a True value.  This
      these settings are overridden by specifying apps on the command
      line.
    * If tests are run with --verbosity=2 or higher, the time taken to
      run each test will be displayed in microseconds.
      """

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """ Test runner that only runs tests for the apps
        not listed in ``settings.EXCLUDED_TEST_APPS`` unless ``TEST_ALL_APPS``
        is set or apps are specified on the command line.  This also
        automatically ignores all ``django.contrib`` apps, regardless of
        the state of ``TEST_ALL_APPS``."""

        if not test_labels:
            excluded_apps = getattr(settings, 'EXCLUDED_TEST_APPS', [])
            if getattr(settings, 'TEST_ALL_APPS', False):
                excluded_apps = []
            test_labels = [x.split('.')[-1] for x in settings.INSTALLED_APPS
                           if x not in excluded_apps
                           and not x.startswith('django.contrib.')]

        return super(HotRunner, self).run_tests(test_labels, extra_tests, **kwargs)

    def run_suite(self, suite, **kwargs):
        return _TimeLoggingTestRunner(
            verbosity=self.verbosity,
            failfast=self.failfast
        ).run(suite)


class HotRunnerTestResult(TextTestResult):

    def getDescription(self, test):
        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            return '\n'.join((str(test), doc_first_line))
        else:
            test = re.findall('[\w_]+', str(test))
            template = '{testname} ({app}.{suite}.{testname})'
            return template.format(app=test[1], suite=test[-1], testname=test[0])

    @property
    def xunit_filename(self):
        hxf = getattr(settings, 'HOTRUNNER_XUNIT_FILENAME', None)
        juxf = getattr(settings, 'JUXD_FILENAME', None)
        return hxf or juxf

    def startTest(self, test):
        self.case_start_time = time.time()
        super(HotRunnerTestResult, self).startTest(test)

    def addSuccess(self, test):
        self.case_time_taken = time.time() - self.case_start_time
        if self.xunit_filename:
            self._make_testcase_element(test)
        super(HotRunnerTestResult, self).addSuccess(test)

    def addFailure(self, test, err):
        self.case_time_taken = time.time() - self.case_start_time
        if self.xunit_filename:
            self._make_testcase_element(test)
            self._add_tb_to_test(test, err)

        super(HotRunnerTestResult, self).addFailure(test, err)

    def addError(self, test, err):
        self.case_time_taken = time.time() - self.case_start_time
        if self.xunit_filename:
            self._make_testcase_element(test)
            self._add_tb_to_test(test, err)

        super(HotRunnerTestResult, self).addError(test, err)

    def addUnexpectedSuccess(self, test):
        self.case_time_taken = time.time() - self.case_start_time
        if self.xunit_filename:
            self._make_testcase_element(test)
        super(HotRunnerTestResult, self).addUnexpectedSuccess(test)

    def addSkip(self, test, reason):
        self.case_time_taken = time.time() - self.case_start_time
        if self.xunit_filename:
            self._make_testcase_element(test)
        super(HotRunnerTestResult, self).addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.case_time_taken = time.time() - self.case_start_time
        if self.xunit_filename:
            self._make_testcase_element(test)
            self._add_tb_to_test(test, err)

        super(HotRunnerTestResult, self).addExpectedFailure(test, err)

    def startTestRun(self):
        if self.xunit_filename:
            with open(self.xunit_filename, 'w') as f:
                f.write('<html>')
            f.close()
        self.run_start_time = time.time()
        super(HotRunnerTestResult, self).startTestRun()

    def stopTestRun(self):
        run_time_taken = time.time() - self.run_start_time

        if self.xunit_filename:
            with open(self.xunit_filename, 'a') as f:
                f.write('<h1>Result:</h1>')
                f.write('<ul>')
                f.write('<li>name: Dispatch</li>')
                f.write(
                    '<li>errors: {0}</li>'.format(self.errors))
                f.write(
                    '<li>failures: {0}</li>'.format(self.failures))
                f.write(
                    '<li>skips: {0}</li>'.format(self.skipped))
                f.write(
                    '<li>tests: {0}</li>'.format(self.testsRun))
                f.write(
                    '<li>time: {0}</li>'.format(run_time_taken))
                f.write('</ul>')
            f.close()

        if self.xunit_filename:
            with open(self.xunit_filename, 'a') as f:
                f.write('</html>')
            f.close()

        super(HotRunnerTestResult, self).stopTestRun()

    def _make_testcase_element(self, test):
        #time_taken = time.time() - self.case_start_time
        classname = ('%s.%s' %
                     (test.__module__, test.__class__.__name__)).split('.')

        if self.xunit_filename:
            with open(self.xunit_filename, 'a') as f:
                f.write('<div>')
                f.write('<font color="green">')
                f.write('time - {0}; '.format(self.case_time_taken))
                f.write('classname - {0}; '.format('.'.join(classname)))
                f.write('name - {0}; '.format(test._testMethodName))
                f.write('</font>')
                f.write('</div>')
                f.close()

    def _add_tb_to_test(self, test, err):
        '''Add a traceback to the test result element'''
        exc_class, exc_value, tb = err
        tb_str = self._exc_info_to_string(err, test)

        if self.xunit_filename:
            with open(self.xunit_filename, 'a') as f:
                f.write('<font color="red">')
                f.write('<p>message - {0}</p>'.format(str(exc_value)))
                f.write('<p>type - {0} {1}</p>'.format(
                    exc_class.__module__, exc_class.__name__))
                f.write('<p>text - {0}</p>'.format(tb_str))
                f.write('</font>')
                f.close()


class _TimeLoggingTestRunner(TextTestRunner):
    resultclass = HotRunnerTestResult
