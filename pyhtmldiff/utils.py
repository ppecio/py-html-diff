# -*- coding: utf-8 -*-

"""Created on 23.06.17

.. moduleauthor:: Paweł Pecio

"""


def ilongzip(a, b):
    """Like `izip` but yields `None` for missing items."""
    aiter = iter(a)
    biter = iter(b)
    try:
        for item1 in aiter:
            yield item1, next(biter)
    except StopIteration:
        for item1 in aiter:
            yield item1, None
    else:
        for item2 in biter:
            yield None, item2


def irepeat(a, b):
    biter = iter(b)

    for item in biter:
        yield a, item
