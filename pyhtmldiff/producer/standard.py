# -*- coding: utf-8 -*-

"""Created on 23.06.17

.. moduleauthor:: Paweł Pecio

"""
import base64
import json
import re
import warnings
from difflib import SequenceMatcher

from genshi.core import QName, Attrs

from pyhtmldiff.dtd.const import DOMNode
from pyhtmldiff.utils import longzip
from .base import DiffProducer


class DefaultDiffProducer(DiffProducer):

    diff_attrs = {
        # for all elements diff style attribute
        '*': {'style', },

        # diff also class attributes for following elements (commonly used to style text)
        'span': {'class', },
        'p': {'class', },

        # diff tables
        'td': {'colspan', 'rowspan'}
    }

    re_css_split = re.compile(r'''((?:[^;)"']|"[^"]*"|'[^']*'|\([^)]*\))+)''')

    @classmethod
    def _diff_item_replace(cls, old_items, new_items):
        result = []
        for idx, (old_item, new_item) in enumerate(longzip(old_items, new_items)):
            if old_item is not None:
                result.append(cls._diff_item_remove(old_item))
            if new_item is not None:
                result.append(cls._diff_item_insert(new_item))

        return result

    @classmethod
    def _diff_item_remove(cls, rule):
        return '-{}'.format(rule)

    @classmethod
    def _diff_item_insert(cls, rule):
        return '+{}'.format(rule)

    @classmethod
    def _diff_item_unchanged(cls, rule):
        return ' {}'.format(rule)

    @classmethod
    def _diff_items(cls, old_items, new_items):
        result = []

        matcher = SequenceMatcher(old_items, new_items)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                result.extend(cls._diff_item_replace(old_items[i1:i2], new_items[j1:j2]))
            elif tag == 'delete':
                for x in range(i1, i2):
                    result.append(cls._diff_item_remove(old_items[x]))
            elif tag == 'insert':
                for x in range(i1, i2):
                    result.append(cls._diff_item_insert(new_items[x]))
            else:
                for x in range(i1, i2):
                    result.append(cls._diff_item_unchanged(old_items[x]))

        return result

    @classmethod
    def _diff_attr(cls, attr_name, old_node, new_node, differ):
        """
        Return diff of attribute ready to be placed in genshi attrs.
        :param attr_name:   Attribute name
        :param old_node:    Old node
        :param new_node:    New node
        :param differ:      Function which should be used to calculate diff
        :type attr_name: basestring
        :type old_node: DOMNode
        :type new_node: DOMNode
        :rtype: basestring
        :return: base64 encoded diff
        """
        old_value = old_node.get(attr_name)
        new_value = new_node.get(attr_name)

        if old_value == new_value:
            return None

        return base64.b64encode('\n'.join(differ(old_value, new_value)))

    @classmethod
    def _get_whole_value_diff(cls, old_value, new_value):
        """
        Returns diff of two values. Do not analyse these values.
        :param old_value:
        :param new_value:
        :rtype tuple:
        :return:
        """
        diff = []
        if old_value == new_value:
            return ' {}'.format(new_value),

        if old_value:
            diff.append('-{}'.format(old_value))

        if new_value:
            diff.append('+{}'.format(new_value))

        return tuple(diff)

    @classmethod
    def _get_css_diff(cls, old_value, new_value):
        """
        Returns diff of CSS rules (any semicolon delimited items, where semicolon is not in quotes or parenthesis).
        See re_css_split regexp for more details.
        :param old_value:
        :param new_value:
        :return:
        """
        old_value = cls.re_css_split.split(old_value)[1::2]
        new_value = cls.re_css_split.split(new_value)[1::2]
        return cls._diff_items(old_value, new_value)

    @classmethod
    def _get_class_diff(cls, old_value, new_value):
        """
        Return diff of classes names (in fact any space delimited items)
        :param old_value:
        :param new_value:
        :return:
        """
        old_class = old_value.split(' ')
        new_class = new_value.split(' ')
        return cls._diff_items(old_class, new_class)

    @classmethod
    def _diff_attr_rowspan(cls, old_node, new_node):
        """
        Returns diff of <rowspan> attribute
        :param old_node:
        :param new_node:
        :type old_node: DOMNode
        :type new_node: DOMNode
        :return:
        """
        return cls._diff_attr('rowspan', old_node, new_node, cls._get_whole_value_diff)

    @classmethod
    def _diff_attr_colspan(cls, old_node, new_node):
        """
        Returns diff of <colspan> attribute
        :param old_node:
        :param new_node:
        :type old_node: DOMNode
        :type new_node: DOMNode
        :return:
        """
        return cls._diff_attr('colspan', old_node, new_node, cls._get_whole_value_diff)

    @classmethod
    def _diff_attr_class(cls, old_node, new_node):
        """
        Returns diff of <class> attribute
        :param old_node:
        :param new_node:
        :type old_node: DOMNode
        :type new_node: DOMNode
        :return:
        """

        return cls._diff_attr('class', old_node, new_node, cls._get_class_diff)

    @classmethod
    def _diff_attr_style(cls, old_node, new_node):
        """
        Returns diff of <style> attribute
        :param old_node:
        :param new_node:
        :type old_node: DOMNode
        :type new_node: DOMNode
        :return:
        """
        return cls._diff_attr('style', old_node, new_node, cls._get_css_diff)

    @classmethod
    def same_opening_node(cls, old_node, new_node):
        """
        Produce diff of the same node types in both versions, but attributes can be different.
        Works on opening tags.

        .. code-block:: html

            <span style="font-size: 10pt"> . . . </span>
            <span style="font-size: 12pt"> . . . </span>

        :param old_node:
        :param new_node:
        :type old_node: DOMNode
        :type new_node: DOMNode
        :rtype DOMNode:
        :return:
        """

        attrs_to_diff = cls.diff_attrs['*'] if '*' in cls.diff_attrs else set()

        if new_node.name in cls.diff_attrs:
            attrs_to_diff = attrs_to_diff & cls.diff_attrs[new_node.name]

        result_node = DOMNode(
            new_node.name,
            new_node.attrs
        )

        for attr in attrs_to_diff:
            differ = getattr(cls, '_diff_attr_{}'.format(attr), None)
            if differ is None:
                warnings.warn("No differ function defined for attribute {}".format(attr))
                continue

            result = differ(old_node, new_node)
            if result is None:
                continue

            result_node.attrs |= [('x-diff-{}'.format(attr), result)]

        return result_node

    @classmethod
    def render_formatting_delete(cls, parent_node, formatting_node):
        attrs = base64.b64encode(json.dumps(formatting_node.attrs))
        return DOMNode(
            name='del',
            attrs=(
                ('class', "formatting"),
                ('x-diff-node', formatting_node.name),
                ('x-diff-attrs', attrs)
            )
        )

    @classmethod
    def render_formatting_insert(cls, parent_node, formatting_node):
        return DOMNode(
            name='ins',
            attrs=(
                ('class', "formatting"),
            )
        )

    @classmethod
    def render_delete(cls, parent_node):
        return DOMNode(
            name='del',
            attrs=()
        )

    @classmethod
    def render_insert(cls, parent_node):
        return DOMNode(
            name='ins',
            attrs=()
        )
