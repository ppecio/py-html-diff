# -*- coding: utf-8 -*-

"""Created on 23.06.17

.. moduleauthor:: Paweł Pecio

"""


class DiffProducer(object):

    @classmethod
    def render_insert(cls, parent_node):
        raise NotImplementedError()

    @classmethod
    def render_delete(cls, parent_node):
        raise NotImplementedError()

    @classmethod
    def render_formatting_insert(cls, parent_node, formatting_node):
        raise NotImplementedError()

    @classmethod
    def render_formatting_delete(cls, parent_node, formatting_node):
        raise NotImplementedError()
