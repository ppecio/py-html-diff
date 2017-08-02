# -*- coding: utf-8 -*-

"""Created on 28.06.17

.. moduleauthor:: Paweł Pecio
"""
import logging
import warnings

from genshi.core import START, END

from differ.buffer import DiffBuffer, Buffer
from differ.iterator import OneBackIterator
from dtd.const import DiffBehaviour
from dtd.html5 import Html5Definition

logger = logging.getLogger('pyHtmlDiff')


class BaseProcessor(object):
    """
    Diff events processor base class
    """

    def __init__(self, events_iter, parent):
        """
        :param events_iter: Diff events iterator
        :param parent: Parent tag in which result of this processor will be appended
        :type events_iter: DiffIterator
        :type parent: QName, None

        """
        self._iter = events_iter
        self._parent = parent
        self._result = self._create_buffer()
        self._exhausted = True
        logger.debug("Diff context processor %r instantiated within parent %r" % (self.__class__, parent))

    def __iter__(self):
        """
        Iterates over diff events. If event cannot be processed by this processor is yielded
        and should be processed by the parent processor. When context of this processor ends
        iteration is stopped

        :raises StopIteration: Processing has been finished by this processor. Diff events iterator
        points just before event which does not belong to this processor work scope
        """
        self._exhausted = False
        for operation, event in self._iter:
            if self._stop(operation, event):
                self._iter.go_back()
                break

            result = self._process_event(operation, event)
            if result is False:
                yield operation, event, self._get_current_element()

        self._exhausted = True
        raise StopIteration

    def _create_buffer(self):
        return Buffer()

    def _get_current_element(self):
        return self._result.get_current_element()

    def _stop(self, operation, event):
        """
        Check condition when iteration of diff events should be stopped.
        See _process_event() method documention for more details about the parameters.

        :param operation:
        :param event:

        :return: True if processing should be ended, False otherwise
        :rtype: bool
        """
        raise NotImplementedError()

    def _process_event(self, operation, event):
        """
        Process diff stream event

        +----------------+------------------------+
        | Operation code | Event                  |
        +----------------+------------------------+
        | insert         | (None, New event       |
        | delete         | (Old event, None)      |
        | equal          | (Old event, New event) |
        | replace        | (old event, new_event) |
        +----------------+------------------------+

        Note: for equal operation old event and new event are the same.

        :param operation: Operation code, can be: insert, delete, replace, equal
        :param event: Genshi event

        :return: True if event was processed, False if processing on this event is not supported
        and should be taken by parent processor
        :rtype: bool
        """

        ev = None

        if operation in {'equal', 'insert'}:
            ev = event[1]
        elif operation == 'delete':
            ev = event[0]
        elif operation == 'replace':
            ev = event[1]
            if ev is None:
                return True
        else:
            raise NotImplementedError("Unsupported operation")

        ev_type, data, pos = ev

        if ev_type == START:
            dt = Html5Definition.get_diff_type(data[0])

            if dt in {DiffBehaviour.as_block, DiffBehaviour.skip}:
                return False

        return True

    def inject(self, buff):
        """
        Inject result of another processor
        :param buff:
        :return:
        """
        raise NotImplementedError()

    def flush(self):
        """
        Finalize processing and returns processor result.
        Can be called only when processor is exhausted, which means iteration is over
        :return:
        """
        assert self._exhausted, "Processor is in mid of operation. Cannot flush, because result is not ready"
        return self._result


class RootProcessor(BaseProcessor):
    """
    Root processor takes fresh diff iterator and process all events.
    If diff operation is detected control is routed to appropriate special processor.
    """

    def __init__(self, diff_iter):
        diff_iter = OneBackIterator(diff_iter)
        super(RootProcessor, self).__init__(diff_iter, None)

    def _stop(self, operation, event):
        # never stops, root processor run over all events
        return False

    def _subprocess_event(self, operation, event, parent=None):

        if operation == 'equal':
            processor_cls = EqualProcessor
            this_ev = event[1]
        elif operation == 'insert':
            processor_cls = InsertProcessor
            this_ev = event[1]
        elif operation == 'delete':
            processor_cls = DeleteProcessor
            this_ev = event[0]
        elif operation == 'replace':
            processor_cls = ReplaceProcessor

            # TODO: which event should be taken? what if block diffed element is replaced by internally
            # diffed?
            this_ev = event[1]
        else:
            raise AssertionError("Unsupported operation type %r" % operation)

        # TODO: this_ev could be None even if replace operation contain None as new element
        if this_ev is not None and this_ev[0] == START:
            diff_type = Html5Definition.get_diff_type(this_ev[1][0])
            if diff_type == DiffBehaviour.skip:
                processor_cls = SkipProcessor
            elif diff_type == DiffBehaviour.as_block:
                processor_cls = BlockProcessor

        # rewind iterator one step back, so processor will the this event as a first one
        self._iter.go_back()

        logger.debug("-> Entering into processor %r" % processor_cls)

        processor = processor_cls(self._iter, parent=(parent or self._get_current_element()))
        for op, evt, parent in processor:
            processor.inject(self._subprocess_event(op, evt, parent))

        res = processor.flush()

        logger.debug('<- Processor %r left' % processor_cls)
        return res

    def _process_event(self, operation, event):
        self._result.extend(self._subprocess_event(operation, event).get_result())

    def execute(self):
        for _ in self:
            # root processor should never yield
            raise AssertionError

        return self.flush().get_result()

    def inject(self, buff):
        # This is root processor, there is no processor which can inject something
        raise NotImplementedError("Injection into root processor is not allowed")


class BlockProcessor(BaseProcessor):
    """
    Block processor process block content, which are nodes which should not be diffed internally.
    * if whole block is equal then block is equal,
    * if block opening tag is removed then whole block is removed
    * if opening tag is inserted, whole block is inserted,
    * if opening tag is replaced, then whole block is replaced (should be duplicated with contents)
    * if block contents was modified, whole block should be marked ad replaced (should be duplicated)
    """

    def __init__(self, *args, **kwargs):
        super(BlockProcessor, self).__init__(*args, **kwargs)
        self._op_codes = set()
        self._started = False

    def _create_buffer(self):
        return (
            DiffBuffer(operation='delete', parent=self._parent),
            DiffBuffer(operation='insert', parent=self._parent)
        )

    def _stop(self, operation, event):
        # when stack is cleared then stop processing
        # started flag prevents cancelling operation in first iteration when opening node tag is
        # not in the result stack yet
        if self._started is False:
            self._started = True
            return False

        return self._result[0].is_stack_empty() and self._result[1].is_stack_empty()

    def inject(self, buff):
        # Injecting make no sense, because this processor is able to process all operations
        # (it never yields)
        raise NotImplementedError("Injecting into skipped content is not allowed")

    def _process_event(self, operation, event):

        # passthrough to the output all events which comes from new version

        self._op_codes.add(operation)

        if operation in {'equal', 'replace'}:
            if event[0] is not None:
                self._result[0].append(event[0])
            if event[1] is not None:
                self._result[1].append(event[1])
        elif operation == 'delete':
            self._result[0].append(event[0])
        elif operation == 'insert':
            self._result[1].append(event[1])
        else:
            raise NotImplementedError("Unknown operation")

        return True

    def flush(self):
        if len(self._op_codes) == 1:
            code = self._op_codes.pop()
            if code == 'equal':
                # this is block diff, if result contain diff tags than opening node is
                # the first element in the result, closing is the last one - remove them
                # because content is equal so should not be marked
                buff = Buffer()
                buff.inject(self._result[1].get_result()[1:-1])
                return buff
            elif code == 'delete':
                return self._result[0]
            elif code == 'insert':
                return self._result[1]

        # if block opening tag was replaced or block contents has insertion/removals/replacements
        # whole block should be marked as replaced, which means that old content should be marked as
        # removed, new one as inserted. Concatenate result from two buffers
        buff = Buffer()
        buff.inject(self._result[0].get_result())
        buff.inject(self._result[1].get_result())
        return buff


class SkipProcessor(BaseProcessor):
    """
    Skip processor process content (nodes) which should be skipped, which means that should not
    be diffed. New version of the content is just passed to the result without any processing.

    This is kind of block processor but with no processing logic.
    """

    def __init__(self, *args, **kwargs):
        super(SkipProcessor, self).__init__(*args, **kwargs)
        self._started = False

    def _stop(self, operation, event):
        # when stack is cleared then stop processing
        # started flag prevents cancelling operation in first iteration when opening node tag is
        # not in the result stack yet
        if self._started is False:
            self._started = True
            return False

        return self._result.is_stack_empty()

    def inject(self, buff):
        # Injecting make no sense, because this processor is able to process all operations
        # (it never yields)
        raise NotImplementedError("Injecting into skipped content is not allowed")

    def _process_event(self, operation, event):

        # passthrough to the output all events which comes from new version

        if operation != 'remove':
            # append event from new version for equal, insert and replace
            self._result.append(event[1])

        # if operation is remove do nothing, removed content should not be included in the result
        # there is no need to track opening and closing of removed content, if opening tag is removed
        # then closing tag is removed too

        return True


class EqualProcessor(BaseProcessor):

    def inject(self, buff):
        # in equal context all results can be placed as is, without any processing
        self._result.extend(buff.get_result())

    def _stop(self, operation, event):
        return operation != 'equal' and self._result.is_stack_empty()

    def _process_event(self, operation, event):

        if not super(EqualProcessor, self)._process_event(operation, event):
            return False

        if operation != 'equal':
            # if operation is different than equal cannot be handled by this processor,
            # return False which means that operation will be yielded and passed to the parent
            # processor
            return False

        self._result.append(event[0])


class SingleOperationProcessor(BaseProcessor):

    operation = None

    def inject(self, buff):
        if isinstance(buff, DiffBuffer):
            if buff.operation != self.operation:
                # another diff buffer is injecting, if operation is the same allow, if is different
                # currently result is not defined
                warnings.warn("Cannot inject buffer which describe different operation than handled "
                              "by current processor")

        res = buff.get_result()
        if res[0][0] == START and res[0][1][0] in {'ins', 'del'}:
            # this is block result (probably), remove wrapping diff tag to avoid
            # putting diff tag in diff tag
            res = res[1:-1]

        self._result.extend(res)

    def _stop(self, operation, event):
        if operation != self.operation and self._result.is_stack_empty():
            return True

        return False

    def _create_buffer(self):
        return DiffBuffer(operation=self.operation, parent=self._parent)

    def _process_event(self, operation, event):

        if not super(SingleOperationProcessor, self)._process_event(operation, event):
            return False

        if operation == 'equal' or operation == self.operation:
            self._result.append(
                self._select_event(event)
            )
        else:
            return False


class InsertProcessor(SingleOperationProcessor):
    operation = 'insert'

    def _select_event(self, evts):
        return evts[1]


class DeleteProcessor(SingleOperationProcessor):
    operation = 'delete'

    def _select_event(self, evts):
        return evts[0]


class ReplaceProcessor(BaseProcessor):
    operation = 'replace'

    def inject(self, buff):
        if isinstance(buff, DiffBuffer):
            if buff.operation == 'insert':
                self._result[1].extend(buff.get_result())
            elif buff.operation == 'delete':
                self._result[0].extend(buff.get_result())
            else:
                raise NotImplementedError("Not supported diff buffer injection")
        else:
            self._result[0].extend(buff.get_result())
            self._result[1].extend(buff.get_result())

    def _stop(self, operation, event):
        if operation != 'replace' and self._result[0].is_stack_empty() and self._result[1].is_stack_empty():
            return True

        return False

    def _create_buffer(self):
        return (
            DiffBuffer(operation='delete', parent=self._parent),
            DiffBuffer(operation='insert', parent=self._parent)
        )

    def _process_event(self, operation, event):

        if not super(ReplaceProcessor, self)._process_event(operation, event):
            return False

        if operation in {'equal', 'replace'}:
            if event[0] is not None:
                self._result[0].append(event[0])
            if event[1] is not None:
                self._result[1].append(event[1])
        elif operation == 'delete':
            self._result[0].append(event[0])
        elif operation == 'insert':
            self._result[1].append(event[1])
        else:
            raise NotImplementedError("Unsupported operation")

        return True

    def flush(self):
        buff = Buffer()
        buff.inject(self._result[0].get_result())
        buff.inject(self._result[1].get_result())
        return buff

    def _get_current_element(self):
        # TODO: if both current elements are the same case is simple
        # but what if are different?
        return self._result[1].get_current_element()
