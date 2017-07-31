# -*- coding: utf-8 -*-

"""Created on 28.06.17

.. moduleauthor:: Paweł Pecio
"""
import re
import string
from difflib import SequenceMatcher
from itertools import chain, islice

from genshi.core import TEXT

from utils import ilongzip, irepeat


class SplittedTextNodesIterator(object):
    """
    By default Genshi events are emitted per text node. This library diffs text nodes
    by words so split text node by whitespaces and emit text node event per each word.
    """

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
        # return splitted text node, also return splitting delimiter (whitespace), to keep the same
        # whitespaces in the result
        return self._diff_split_re.split(text)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]


class ReplaceIterator(object):
    """
    Convert replace operation from stream differ to delete and insert operation.
    Here should be all magic with grouping/un-grouping inserts and removals during modify operation.
    """

    def __init__(self, old_part, new_part):
        self._iter = OneBackIterator(ilongzip(old_part, new_part))
        self._items = None

    def _fill(self):
        stop = False
        old = []
        new = []

        while not stop:
            # Replace operation should be rendered as remove and insert operations, convert
            # one replace to these operations. Often replace is over multiple elements (events),
            # try to group removals and inserts, so for example changing two words in text will be
            # rendered as removing od old two words followed by insertion of new two words instead of
            # first word removal, first word insertion and second word removal, second word insertion

            # The same concern nodes, but for nodes operation is more complex and not implemented yet
            # TODO: implement grouping for nodes (algorithm needs to be developed)

            try:
                old_evt, new_evt = next(self._iter)
            except StopIteration:

                # if there is no collected events (wrapped iterator is exhausted), re-raise exception
                if not old and not new:
                    raise

                # ... otherwise break the loop and return collected events
                break

            if old_evt:
                old.append(('delete', old_evt))
            if new_evt:
                new.append(('insert', new_evt))

            stop = (old_evt is not None and old_evt[0] != TEXT) or (new_evt is not None and new_evt[0] != TEXT)

        self._items = iter(old + new)

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
    """
    Wrapper for sequence matcher which convert its result to iterator which wraps
    insert, removals and replaces into one standard diff item.

    This iterator is filling iterator buffer by parts by taking one op code from
    sequence matcher iterator and them processing it (this may produce multiple items).
    When op code part is exhausted, iterator takes next op code.
    """

    def __init__(self, old, new):
        self._old = old
        self._new = new
        matcher = SequenceMatcher(lambda x: x[0] == TEXT and x[1] in string.whitespace, self._old, self._new)
        self._parts = iter(matcher.get_opcodes())

        self._iterator = None

    def _fill(self):
        """
        Get next op code from sequence matcher and render it into iterator buffer.
        :return:
        """

        operation, i1, i2, j1, j2 = next(self._parts)
        if operation == 'replace':
            # match slices to its ends

            skip = (i2 - i1) - (j2 - j1)

            # Sequences should be aligned to its ends for proper prepending and removals at the begging
            # handling.
            #
            # This is caused by how SequenceMatcher works. If old events list is shorted then
            # new events list there are three cases:
            #   1) contents has been changed and there is no common parts
            #      In this case all old data should be marked as removed and all new as inserted. How this
            #      iterator match items from old and new lists make no difference because in fact none of items
            #      are matching
            #   2) new content has been prepended to existing and old items list contains usually one item
            #      For example if text was changed from 'awesome text' to 'My awesome text', then SequenceMatcher
            #      generate replace op_code [('awesome'), ('My', 'awesome')] and equal op_code [('text'), ('text')]
            #      In this case to avoid removal mark on 'awesome' word and insertion for 'My awesome' ilongzip
            #      iterator should return (None, 'My') and ('awesome', 'awesome') items (so align lists to its ends)
            #   3) content has been removed from the begging
            #      For example if text was changed from 'My awesome' to 'awesome', SequenceMatcher generate replace
            #      op_code [('My', 'awesome'), ('awesome')]. This is a dual case for #2.
            #
            #   If contents has been changed but there are matching parts, this will be discovered by SequenceMatcher
            #   and won't be returned with single op_code.

            #   If user appends/removes contents at the end SequenceMatcher detect this correctly.

            old_part = islice(self._old, i1, i2)
            new_part = islice(self._new, j1, j2)

            if skip < 0:
                # new list is longer than old
                old_part = OffsetIterator(old_part, abs(skip))
            elif skip > 0:
                # old is longer than new
                new_part = OffsetIterator(new_part, skip)

            iterator = ReplaceIterator(old_part, new_part)
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
            # iterator buffer is empty, fill it by taking next op code sequence from
            # sequence matcher iterator
            self._fill()

        try:
            return next(self._iterator)
        except StopIteration:
            # If iterator buffer is exhausted, clear iterator stack and try again
            # Next attempt should fill the buffer, if sequence matcher operator is also exhausted
            # then fill method raises StopIteration exception which is not handled here
            self._iterator = None
            return self.next()


class OffsetIterator(object):
    """
    Returns n given elements before first real item from given iterator will be returned
    """

    def __init__(self, iter, num, element=None):
        self._iter = iter
        self._num = num
        self._element = element

    def __iter__(self):
        for i in range(0, self._num):
            yield self._element

        for item in self._iter:
            yield item


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
