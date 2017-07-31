# -*- coding: utf-8 -*-

"""
    Created on 17.05.17
    @author: druid
"""
import os
from unittest import skip

import six
import sys
import yaml
import unittest
import logging

from pyhtmldiff import Diff


logger = logging.getLogger('pyHtmlDiff')
logger.setLevel(logging.ERROR)

"""
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
"""


class YamlTestRunnerMeta(type):

    def __new__(mcs, name, bases, attrs):

        directory = attrs.get('directory')
        assert directory is not None, "Fixtures directory not set"
        assert os.path.isdir(directory), "Fixtures directory does not exists: %s" % directory

        def gen_test(case):
            def test(self):
                logger.debug("Starting test %s", case.get('title', '[Unnamed test case]'))
                self.maxDiff = 500

                original = case.get('original', None)
                modified = case.get('modified', None)
                expected = case.get('expected', None)

                self.assertIsNotNone(original, msg="Original text unset")
                self.assertIsNotNone(modified, msg="Modified text unset")
                self.assertIsNotNone(expected, msg="Expected text unset")

                result = self.differ.get_html_diff(original, modified)

                self.assertEqual(expected, result)

            skip_test = case.get('skip', None)
            if skip_test is not None:
                return skip(skip_test)(test)
            else:
                return test

        for filename in os.listdir(directory):
            case_file = open(os.path.join(directory, filename), "r")
            data = yaml.load(case_file)

            for name, case in data.items():
                if name == 'maintainer':
                    continue

                if not isinstance(case, dict):
                    continue

                test_name = 'test_%s_%s' % (filename, name)

                attrs[test_name] = gen_test(case)
                attrs[test_name].__doc__ = case.get('title')

        return type.__new__(mcs, name, bases, attrs)


@six.add_metaclass(YamlTestRunnerMeta)
class YamlTestRunner(unittest.TestCase):

    directory = os.path.dirname(__file__) + '/scenarios'

    differ = Diff()
    maxDiff = 500
