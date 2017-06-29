# -*- coding: utf-8 -*-

"""Created on 23.06.17

.. moduleauthor:: Paweł Pecio

"""
from collections import namedtuple

from flufl.enum import Enum


class DiffBehaviour(Enum):
    # diffing algorithm can go inside this element and analyse element contents, ins/del can be
    # placed as a content
    internally = 1,

    # same as internally, but ins/del cannot be placed as a content (but maybe can be in deeper elements)
    step_inside = 2,

    # element should be treated as one non-splittable object which should be diffed at once without going deeper
    # into the contents
    as_block = 3,

    # skip diff analysing, just copy as is to the output (in whichever version of HTML this element exist)
    skip = 4


DOMNode = namedtuple('DOMNode', [
    # genshi.core.QName
    'name',
    # genshi.core.Attrs
    'attrs'
])
