# -*- coding: utf-8 -*-

"""Created on 28.06.17

.. moduleauthor:: Paweł Pecio
"""
import warnings, logging

from genshi.core import START, END, TEXT, Attrs, QName

from differ.iterator import OneBackIterator
from dtd.const import DiffBehaviour, DOMNode
from dtd.html5 import Html5Definition
from producer.standard import DefaultDiffProducer


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
        self._result = []
        self._stack = []
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
                yield operation, event, self.get_current_element()

        self._exhausted = True
        raise StopIteration

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

        +----------------+-----------+
        | Operation code | Event     |
        +----------------+-----------+
        | insert         | New event |
        | delete         | Old event |
        | equal          | New event |
        +----------------+-----------+

        :param operation: Operation code, can be: insert, delete, replace, equal
        :param event: Genshi event

        :return: True if event was processed, False if processing on this event is not supported
        and should be taken by parent processor
        :rtype: bool
        """

        event_type, data, pos = event
        if event_type == START:
            tag, attrs = data

            # check how these tag should be diffed
            diff_type = Html5Definition.get_diff_type(tag)
            if diff_type == DiffBehaviour.skip:
                # diffing of this tag and its contents should be skipped
                # passthrough whole tag to the output
                self._passthrough(event)
                return True
            elif diff_type == DiffBehaviour.as_block:
                # diff this tag as one element, to do that go through all
                self._process_block(event)
                return True

            self.append(event)
            self._enter(data[0])
        elif event_type == END:
            self._leave(data)
            self.append(event)
        else:
            self.append(event)

        return True

    def _collect_block(self, start_event, op_to_collect):

        event_type, data, pos = start_event
        result = []

        # track how many times the same tag is open inside pass-thorough block
        counter = 1

        for operation, event in self._iter:

            if operation in op_to_collect:
                # only events from new version are important
                result.append(event)

            et, dt, p = event
            if et == START and dt[0] == data[0]:
                # again, inside skipped block the same tag is open, increase tag opening counter
                counter += 1
            elif et == END and dt == data[0]:
                counter -= 1
                if counter == 0:
                    break

        return result

    def _passthrough(self, start_event):
        """
        Pass whole tag and its content just to the output without any processing.
        :param start_event:
        :return:
        """
        self.extend(self._collect_block(start_event, {'equal', 'insert'}))

    def _process_block(self, start_event):
        """
        Check if block (whole tag and its contents) was changed and process it appropriately.
        By default, collect whole block and send to the result at once.
        :param start_event:
        :return:
        """
        raise NotImplementedError()

    def get_current_element(self):
        """
        Get current element which contents are processing
        :return:
        :rtype: QName
        """
        return self._stack[-1] if self._stack else self._parent

    def can_contain_diff(self):
        """
        Determine if current element (see get_current_element()) can hold diff tags
        :return: True if diff tags are allowed as current element contents, False otherwise
        :rtype: bool
        """
        return Html5Definition.get_diff_type(self.get_current_element()) == DiffBehaviour.internally

    def _enter(self, tag):
        logger.debug('  > entering into %r' % tag)
        self._stack.append(tag)

    def pop_stack(self):
        return self._stack.pop() if self._stack else None

    def _leave(self, tag):
        logger.debug('  > trying to leave %r' % tag)

        top = self.pop_stack()

        if top is None:
            warnings.warn("Cannot leave requested tag, stack empty. Tag: %r" % tag)
            return False

        if top == tag:
            return True

        warnings.warn("Close tag request does not match current opened tag. Current: %r, Requested: %r" % (
            top,
            tag
        ))

        return False

    def append(self, result):
        """
        Append given item to the processor result stream
        :param result: tuple(event_type, data, pos)
        :return:
        """
        self._result.append(result)

    def extend(self, result):
        """
        Extends processor result stream by given results
        :param result: list,tuple
        :return:
        """
        self._result.extend(result)

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
        elif operation == 'insert':
            processor_cls = InsertProcessor
        elif operation == 'delete':
            processor_cls = DeleteProcessor
        else:
            raise AssertionError("Unsupported operation type %r" % operation)

        # rewind iterator one step back, so processor will the this event as a first one
        self._iter.go_back()

        logger.debug("-> Entering into processor %r" % processor_cls)

        processor = processor_cls(self._iter, parent=(parent or self.get_current_element()))
        for op, evt, parent in processor:
            processor.extend(self._subprocess_event(op, evt, parent))

        res = processor.flush()

        logger.debug('<- Processor %r left' % processor_cls)
        return res

    def _process_event(self, operation, event):
        res = self._subprocess_event(operation, event)
        self.extend(res)

    def execute(self):
        for _ in self:
            # root processor should never yield
            raise AssertionError

        return self.flush()

    def _process_block(self, start_event):
        raise AssertionError


class EqualProcessor(BaseProcessor):

    def _stop(self, operation, event):
        return operation != 'equal' and not self._stack

    def _process_event(self, operation, event):
        if operation != 'equal':
            return False

        return super(EqualProcessor, self)._process_event(operation, event)

    def _process_block(self, start_event):
        event_type, data, pos = start_event
        old_events = []
        new_events = []
        op_codes = set()

        # track how many times the same tag is open inside pass-thorough block
        counter = 1

        for operation, event in self._iter:

            op_codes.add(operation)

            if operation in {'equal', 'delete'}:
                old_events.append(event)

            if operation in {'equal', 'insert'}:
                new_events.append(event)

            et, dt, p = event
            if et == START and dt[0] == data[0]:
                # again, inside skipped block the same tag is open, increase tag opening counter
                counter += 1
            elif et == END and dt == data[0]:
                counter -= 1
                if counter == 0:
                    break

        if len(op_codes) > 1 or 'equal' not in op_codes:
            # if there was more than one diff operation in block contents or
            # operation is different than equal, then it means that block contents changed,
            # render old as removed, render new as inserted
            processor = DeleteProcessor(parent=self.get_current_element())
            processor.extend(old_events)
            self.extend(processor.flush())
            processor = InsertProcessor(parent=self.get_current_element())
            processor.extend(new_events)
            self.extend(processor.flush())
        else:
            self.extend(new_events)


class SingleOperationProcessor(BaseProcessor):

    class MARKER(object):
        pass

    operation = None

    def __init__(self, *args, **kwargs):
        super(SingleOperationProcessor, self).__init__(*args, **kwargs)
        self._stack = []
        self._buffer = []

        self._rendered = False
        self._all_same = None

        if self.can_contain_diff():
            self.open_diff()

    def _stop(self, operation, event):
        if operation != self.operation and (not self._stack or self._stack[0] is self.MARKER):
            return True

        return False

    def _process_event(self, operation, event):

        if operation == 'equal':
            self._all_same = False
            self.append(event)

        if operation != self.operation:
            self._all_same = False
            return False

        return super(SingleOperationProcessor, self)._process_event(operation, event)

    def _enter(self, tag):
        super(SingleOperationProcessor, self)._enter(tag)

        if self._rendered is True and self.get_current_element() is self.MARKER:
            # if diff tag is open and we are about to enter into new tag
            # and we are in diff tag, close current diff, so
            # Foo <b> bar </b>
            #  I   I   E   I
            # will be rendered as:
            # <ins>Foo</ins><ins formatting><b>E</b></ins>
            #
            self.close_diff()

        if self._rendered is False and self.can_contain_diff():
            self.open_diff()

    def _leave(self, tag):

        if super(SingleOperationProcessor, self)._leave(tag):

            top = self.get_current_element()
            if top is self.MARKER:
                self.pop_stack()
                self.close_diff()

            return True

        return False

    def append(self, result):
        if self._rendered:
            self._buffer.append(result)
        else:
            evt_type, data, pos = result
            if evt_type == TEXT:
                # Diff processor tag is not rendered yet, but text node insertion is requested
                # this means that content visible to user won't be marked properly
                # This may happen only if current node not allow to place diff inside but allow
                # to has content nodes. Probably there is only one such tag in HTML - <pre>
                warnings.warn("Diff tag not rendered and text node is about to be appended to the result."
                              "Text '%r' won't be marked properly" % data)

                if not self._append_hazardous_result():
                    return

            self._result.append(result)

    def extend(self, result):
        if self._rendered:
            self._buffer.extend(result)
        else:
            # Diff processor tag is not rendered yet, but set of results was requested to be inserted
            # at bulk. These results won't be marked properly.
            warnings.warn("Diff tag not rendered and bulk of events is about to be inserted in the result")
            if not self._append_hazardous_result():
                return

            self._result.extend(result)

    def _append_hazardous_result(self):
        """
        Items which are about to be appended will not be properly marked according to the processor,
        because diff tag was not placed yet. By default, such content appending is not allowed.
        :return:
        """
        return False

    def close_diff(self):
        """
        Close diff marked piece of HTML. Detect if all operation events was the same, if so it means that only
        one kind of operation happen, so regular diff tag should be rendered. If operations are not the same
        this means that inside diffed element there is also original content, so in fact this was a change in
        formatting.

        Diffed sections are rendered lazily. Here, opening diff tag is put into result stream, then
        collected buffer events and closing tag.
        """
        # child is an element which should be wrapped by diff, this could be a text node
        # or tag
        child = self._buffer[0]
        if self._all_same:
            # all events was the same operation
            node = getattr(DefaultDiffProducer, 'render_%s' % self.operation)(self.get_current_element())
        else:
            # here text node is not valid, diff in text is by word, its not possible that
            # text nodes are inserted and not all in this context was inserted (if so, diff iterator
            # should return equal action and break insert processor)
            assert child[0] == START
            formatting_node = DOMNode(
                name=child[1][0],
                attrs=child[1][1]
            )
            node = getattr(DefaultDiffProducer, 'render_formatting_%s' % self.operation)(self.get_current_element(),
                                                                                         formatting_node)

        logger.debug("Lazy diff '%s' of %d nodes marked using %r" % (self.operation, len(self._buffer), node))

        self._result.append((START, (QName(node.name), Attrs(node.attrs)), None))
        self._result.extend(self._buffer)
        self._result.append((END, QName(node.name), None))

        self._rendered = False
        self._buffer = []

    def open_diff(self):
        """
        Lazily open diff marked piece of HTML. As now, all results will be stored in temporary buffer until
        opened tags stack return back to diff mark and close_diff() will be called.
        """
        logger.debug("Diff tag allowed in %r. Opening node." % self.get_current_element())
        self._buffer = []
        self._rendered = True
        self._all_same = True
        self._stack.append(self.MARKER)


    def flush(self):
        if self._stack and self._stack[0] is self.MARKER:
            self.close_diff()

        return super(SingleOperationProcessor, self).flush()

    def _process_block(self, start_event):
        raise NotImplementedError()


class InsertProcessor(SingleOperationProcessor):

    operation = 'insert'

    def _append_hazardous_result(self):
        # for insertion processor allow to put hazardous result into output,
        # this is not OK, but only side effect is that content which was inserted in new document version
        # won't be marked as inserted. This case is better that dropping this content completely out.
        return True

    def _process_block(self, start_event):
        # whole block should be marked as inserted, collect sub-events which type is equal or inserted,
        # so block will be rendered in the same way as is in new file version
        self.extend(self._collect_block(start_event, {'equal', 'insert'}))


class DeleteProcessor(SingleOperationProcessor):
    operation = 'delete'

    def _passthrough(self, start_event):
        # node is marked as removed and all its contents should be skipped
        # in deletion it means that should not be passed to the output
        # just consume block
        self._collect_block(start_event, set())

    def _process_block(self, start_event):
        # whole block should be marked as removed, collect contents events which type is equal or deleted,
        # so removed block will be rendered in the same way as exist in old file version
        # skip any insertion inside (if exist) because cannot be rendered (diff is not allowed inside block)
        self.extend(self._collect_block(start_event, {'equal', 'delete'}))
