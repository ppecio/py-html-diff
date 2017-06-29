# -*- coding: utf-8 -*-

"""Created on 26.06.17

.. moduleauthor:: Paweł Pecio
"""
from flufl.enum import Enum


ChangeType = Enum(
    'insertion',
    'removal',
    'formatting'
)
