# -*- coding: utf-8 -*-

"""Created on 28.06.17

.. moduleauthor:: Paweł Pecio
"""
import re
from difflib import SequenceMatcher
from itertools import chain, islice

from genshi.core import TEXT

from utils import longzip, irepeat


class SplittedTextNodesIterator(object):

    _diff_split_re = re.compile(r'(\s+)(?u)')

    def __init__(self, genshi_events):
        self._prepare_events(genshi_events)

    def _prepare_events(self, genshi_events):
        result = []
        for event_type, data, pos in genshi_events:
            if event_type == TEXT:
                for word in self._text_split(data):
                    if word:
                        # only if there is a content
                        result.append((event_type, word, pos))
                continue

            result.append((event_type, data, pos))

        self._data = result

    def _text_split(self, text):
        worditer = chain([u''], self._diff_split_re.split(text))
        return [x + next(worditer) for x in worditer]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]


class ReplaceIterator(object):

    def __init__(self, old_part, new_part):
        self._iter = longzip(old_part, new_part)
        self._items = None

    def _fill(self):
        items = []
        old_evt, new_evt = next(self._iter)
        if old_evt:
            items.append(('delete', old_evt))
        if new_evt:
            items.append(('insert', new_evt))

        self._items = iter(items)

    def __iter__(self):
        return self

    def next(self):
        if self._items is None:
            # fill might throw StopIteration is there is no date to
            # iterate over
            self._fill()

        try:
            return next(self._items)
        except StopIteration:
            # if buffer is exhausted, reset it and re-try
            self._items = None
            return self.next()


class DiffIterator(object):

    def __init__(self, old, new):
        self._old = old
        self._new = new
        matcher = SequenceMatcher(None, self._old, self._new)
        self._parts = iter(matcher.get_opcodes())

        self._iterator = None

    def _fill(self):

        operation, i1, i2, j1, j2 = next(self._parts)
        if operation == 'replace':
            iterator = ReplaceIterator(islice(self._old, i1, i2), islice(self._new, j1, j2))
        elif operation == 'delete':
            iterator = irepeat('delete', islice(self._old, i1, i2))
        elif operation == 'insert':
            iterator = irepeat('insert', islice(self._new, j1, j2))
        else:  # equal
            # both streams slices are the same,
            # it make no difference which stream is taken
            iterator = irepeat('equal', islice(self._old, i1, i2))

        self._iterator = iterator

    def __iter__(self):
        return self

    def next(self):
        if self._iterator is None:
            self._fill()

        try:
            return next(self._iterator)
        except StopIteration:
            self._iterator = None
            return self.next()


class OneBackIterator(object):
    """
    Wrapper iterator which allows to make one step back during iteration.

    Example:
    >>> it = OneBackIterator([1, 2, 3, 4])
    >>> next(it)
    >>> << 1
    >>> next(it)
    >>> << 2
    >>> it.go_back()
    >>> next(it)
    >>> << 2
    >>> next(it)
    >>> << 3
    """

    def __init__(self, iter):
        self._iter = iter
        self._current = None
        self._previous = False

    def __iter__(self):
        return self

    def next(self):
        if self._previous:
            self._previous = False
            return self._current

        item = next(self._iter)
        self._current = item
        return item

    def go_back(self):
        self._previous = True
