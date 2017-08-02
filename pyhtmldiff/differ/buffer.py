# -*- coding: utf-8 -*-

"""Created on 02.08.17

.. moduleauthor:: Paweł Pecio
"""
import warnings

from genshi.core import START, END, QName, Attrs

from dtd.const import DiffBehaviour
from dtd.html5 import Html5Definition
from producer.standard import DefaultDiffProducer


class DiffMarker(object):

    def __init__(self, operation):
        self._operation = operation

    @property
    def operation(self):
        return self._operation


class Buffer(object):

    def __init__(self):
        self._result = []
        self._stack = []

    def append(self, event):

        event_type, data, pos = event

        if event_type == START:
            # opening node tag
            self._open_node(data[0])
        elif event_type == END:
            self._close_node(data)

        self._result.append(event)

    def extend(self, events):
        for ev in events:
            self.append(ev)

    def inject(self, data):
        """
        Unsafe operation to put data into buffer. In opposite to extend() this function does
        not check inserted data and does not validate tag opening and closing nodes.
        :param data:
        :return:
        """
        self._result.extend(data)

    def _open_node(self, data):
        self._stack.append(data)

    def _close_node(self, data):

        if self._stack[-1] != data:
            raise AssertionError("Close request does not match current element")

        self._stack.pop()

    def get_result(self):
        return self._result

    def is_stack_empty(self):
        if not self._stack:
            return True
        elif len(self._stack) == 1 and isinstance(self._stack[0], DiffMarker):
            # if the only item on stack is diff marker, stack is empty
            return True

        return False

    def get_current_element(self):
        return None if self.is_stack_empty() else self._stack[-1]


class DiffBuffer(Buffer):

    renderer = DefaultDiffProducer()

    def __init__(self, operation, parent=None):
        super(DiffBuffer, self).__init__()

        if operation == 'replace':
            raise NotImplementedError("Replace operation is not supported by diff buffer which"
                                      "represents HTML diff object. In HTML only ins and del are allowed")

        self._marker = DiffMarker(operation)
        self._rendered = False
        self._buffer = None

        if parent is None or self.can_contain_diff(parent):
            self._open_diff()

    @property
    def operation(self):
        return self._marker.operation

    def get_result(self):
        if len(self._stack) == 1 and isinstance(self._stack[0], DiffMarker):
            self._close_diff()

        if self._buffer is not None:
            # this might happen if diff was opened but is not closed (even by code above)
            # probably some tag inside diff was not closed properly
            # In fact, with valid HTML, this should never happens
            warnings.warn("Diff buffer is not empty and its content won't be included into the result.")

        return self._result

    def append(self, event):
        if self._buffer is not None:
            self._buffer.append(event)
        else:
            super(DiffBuffer, self).append(event)

    def is_stack_empty(self):
        # if there is opened diff, opened nodes stack is empty if this buffer stack is empty and
        # diff buffer stack is empty
        return super(DiffBuffer, self).is_stack_empty() and (self._buffer is None or self._buffer.is_stack_empty())

    def _open_node(self, data):
        super(DiffBuffer)._open_node(data)
        if self._rendered is False and self.can_contain_diff(data[0]):
            self._open_diff()

    def _close_node(self, data):
        if isinstance(self._stack[-1], DiffMarker):
            self._close_diff()

        super(DiffBuffer)._close_node(data)

    def _open_diff(self):
        self._buffer = Buffer()
        self._stack.append(self._marker)
        self._rendered = True

    def _close_diff(self):
        assert isinstance(self._stack[-1], DiffMarker), "Close diff section requested, but stack is not clear"
        self._stack.pop()

        self._render_diff()

        self._buffer = None
        self._rendered = False

    def _render_diff(self):
        diff_node = getattr(self.renderer, 'render_%s' % self._marker.operation)(self.get_current_element())
        self._result.append((START, (QName(diff_node.name), Attrs(diff_node.attrs)), None))
        self._result.extend(self._buffer.get_result())
        self._result.append((END, QName(diff_node.name), None))

    def can_contain_diff(self, element):
        dt = Html5Definition.get_diff_type(element)
        if dt == DiffBehaviour.internally:
            return True
        elif dt == DiffBehaviour.step_inside:
            return False
        else:
            warnings.warn("Requested diff tag cannot be rendered because such tag was invalid for parents and "
                          "block or skipped node was reached. Result can be invalid")

            # fake rendered flag, so there will no future attempt to place diff tag
            # for example in skipped node there could be a valid tag to place diff, but skipped node (or
            # diffed as block) cannot not contain diffs even if HTML spec allow for diff tags inside
            self._rendered = True

            return False

