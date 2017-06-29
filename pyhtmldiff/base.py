# -*- coding: utf-8 -*-

"""Created on 23.06.17

.. moduleauthor:: Paweł Pecio

"""

import html5lib
from genshi import Stream
from genshi.input import ET

from differ.base import StreamDiffer


class Diff(object):

    """
    Differ class
    """

    def __init__(self, encoding=None):
        self._encoding = encoding

    @classmethod
    def parse_html(cls, html_string):
        """
        Parse given HTML string and retuns Genshi ET object containing DOM tree
        :param html_string:
        :return:
        """
        # TODO: take care of self._encoding
        builder = html5lib.getTreeBuilder('etree')
        parser = html5lib.HTMLParser(tree=builder)
        tree = parser.parseFragment(html_string)

        return ET(tree)

    def get_generic_diff(self, version_a, version_b):
        """
        Returns generic Genshi Stream object with diff calculated on given A and B HTML content
        versions.

        :param version_a:
        :param version_b:
        :return:
        """
        a_html = self.parse_html(version_a)
        b_html = self.parse_html(version_b)

        return self._get_diff_stream(a_html, b_html)

    def get_diff(self, version_a, version_b, format='html'):
        """
        Return diff between version A and B rendered in given format.
        See Genshi stream render method for list of available renders.
        :param version_a:
        :param version_b:
        :param format: By default 'html'
        :return:
        """
        return self.get_generic_diff(version_a, version_b).render(format, encoding=self._encoding)

    def get_html_diff(self, version_a, version_b):
        """
        Return diff between version A and B rendered as HTML string.

        :param version_a:
        :param version_b:
        :return:
        """
        return self.get_diff(version_a, version_b, format='html')

    # -------------------- PRIVATE METHODS ---------------------------

    def _get_differ_class(self):
        return StreamDiffer

    def _get_differ_context(self, a_html, b_html):
        return {
            'old': a_html,
            'new': b_html
        }

    def _get_differ(self, a_html, b_html):
        kwargs = self._get_differ_context(a_html, b_html)
        instance = self._get_differ_class()(**kwargs)
        return instance

    def _get_diff_stream(self, a_html, b_html):
        # note: parsed HTMLs are placed in <DOCUMENT_FRAGMENT> element, skip this fake-root
        return Stream(self._get_differ(a_html, b_html).get_result()[1:-1])
