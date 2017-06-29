# -*- coding: utf-8 -*-

"""Created on 24.06.17

.. moduleauthor:: Paweł Pecio
"""
from differ import RootProcessor
from differ.iterator import DiffIterator, SplittedTextNodesIterator


class StreamDiffer(object):

    def __init__(self, old, new):
        self._old = old
        self._new = new
        self._result = None

    def _execute(self):
        diff = DiffIterator(
            old=SplittedTextNodesIterator(self._old),
            new=SplittedTextNodesIterator(self._new)
        )

        processor = RootProcessor(diff)
        return processor.execute()

    def get_result(self):
        if self._result is None:
            self._result = self._execute()

        return self._result
