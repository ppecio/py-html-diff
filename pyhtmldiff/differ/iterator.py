# -*- coding: utf-8 -*-

"""Created on 28.06.17

.. moduleauthor:: Paweł Pecio
"""
import re
import string
from collections import namedtuple
from difflib import SequenceMatcher
from itertools import chain, islice

from genshi.core import TEXT, START

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


class OpCodeItem(object):

    def __init__(self, operation, i1, i2, j1, j2):
        self._op = operation
        self._i1 = i1
        self._i2 = i2
        self._j1 = j1
        self._j2 = j2

    @property
    def operation(self):
        return self._op

    @property
    def old_start(self):
        return self._i1

    @property
    def old_end(self):
        return self._i2

    @property
    def new_start(self):
        return self._j1

    @property
    def new_end(self):
        return self._j2

    @property
    def old_length(self):
        return self._i2 - self._i1

    @property
    def new_length(self):
        return self._j2 - self._j1


class OpCodeIterator(object):

    def __init__(self, opcodes):
        self._iter = iter(opcodes)
        self._moves = []
        self._current = None
        self._stack = []

    def __iter__(self):
        return self

    def next(self):
        """

        :return: OpCodeItem
        """
        try:
            self._current = self._stack.pop(0) if self._stack else OpCodeItem(*next(self._iter))
        except StopIteration:
            self._current = None
            raise

        if self._moves:
            mv = self._moves.pop(0)
            self._current._i1 += mv[0]
            self._current._i2 += mv[1]
            self._current._j1 += mv[2]
            self._current._j2 += mv[3]

        return self._current

    def look_ahead(self, offset=1):
        """

        :param offset:
        :return: OpCodeItem
        """
        for i in range(0, offset):
            try:
                self._stack.append(OpCodeItem(*next(self._iter)))
            except StopIteration:
                return None

        return self._stack[-1]

    def move_next(self, offset):
        # cut current element end
        self._current._i2 += offset
        self._current._j2 += offset

        # move next element by the offset
        self._moves.append(
            (offset, offset, offset, offset)
        )

        # element after next element start should be extended by the offset
        self._moves.append(
            (offset, 0, offset, 0)
        )


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
        self._parts = OpCodeIterator(matcher.get_opcodes())

        self._iterator = None

    def _next_part(self):
        return next(self._parts)

    def _fill(self):
        """
        Get next op code from sequence matcher and render it into iterator buffer.
        :return:
        """

        current = self._next_part()
        upcoming = self._parts.look_ahead(1)

        # special case
        # if HTMl element contains multiple child of the same type then if middle child is
        # removed sequence matcher see the same opening tag in old (opening tag of removed element)
        # and new version (opening tag of next element of the same type). In such case sequence matcher
        # keep opening tag as EQUAL and then in delete op_code content, closing tag and opening tag is
        # stored. For proper operation we should move del op_code one event back.
        # Dual situation does not occur for insertions, because sequence matcher mark first occurrence
        # as inserted, not equal.

        if upcoming is not None:
            if current.operation == 'equal' and upcoming.operation == 'delete':
                eual_last_event = self._old[current.old_end - 1]
                del_last_event = self._old[upcoming.old_end - 1]
                if eual_last_event[0] == START and del_last_event[0] == START and eual_last_event[1] == del_last_event[1]:
                    self._parts.move_next(-1)

        old_part = islice(self._old, current.old_start, current.old_end)
        new_part = islice(self._new, current.new_start, current.new_end)

        if current.operation == 'replace':
            # match slices to its ends

            skip = current.old_length - current.new_length

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

            if skip < 0:
                # new list is longer than old
                old_part = OffsetIterator(old_part, abs(skip))
            elif skip > 0:
                # old is longer than new
                new_part = OffsetIterator(new_part, skip)

            iterator = irepeat('replace', ilongzip(old_part, new_part))
        elif current.operation == 'delete':
            iterator = irepeat('delete', ilongzip(old_part, [None]*current.old_length))
        elif current.operation == 'insert':
            iterator = irepeat('insert', ilongzip([None]*current.new_length, new_part))
        else:  # equal
            # both streams slices are the same,
            # it make no difference which stream is taken
            iterator = irepeat('equal', ilongzip(old_part, new_part))

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
