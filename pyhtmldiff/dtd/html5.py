# -*- coding: utf-8 -*-

"""Created on 23.06.17

.. moduleauthor:: Paweł Pecio

"""
from .const import DiffBehaviour


class Html5Definition(object):
    """
    Html5 content types and inheritance
    """

    DIFF_TYPE = {

        # =============== SECTIONING ===================
        # https://www.w3.org/TR/html5/sections.html#sections
        'article': DiffBehaviour.internally,
        'section': DiffBehaviour.internally,
        'nav': None,   # not supported
        'aside': None, # not supported
        'h1': DiffBehaviour.internally,
        'h2': DiffBehaviour.internally,
        'h3': DiffBehaviour.internally,
        'h4': DiffBehaviour.internally,
        'h5': DiffBehaviour.internally,
        'h6': DiffBehaviour.internally,
        'header': DiffBehaviour.internally,
        'footer': DiffBehaviour.internally,
        'address': DiffBehaviour.internally,

        # ================= GROUPING ====================
        # https://www.w3.org/TR/html5/grouping-content.html#grouping-content
        'p': DiffBehaviour.internally,
        # hr does not accept any content inside
        'hr': DiffBehaviour.as_block,
        # pre element does not accept HTML markup inside, can be diffed only as a block, ins/del inside not allowed
        'pre': DiffBehaviour.as_block,
        'blockquote': DiffBehaviour.internally,
        'ol': DiffBehaviour.step_inside,
        'ul': DiffBehaviour.step_inside,
        'li': DiffBehaviour.internally,
        'dl': DiffBehaviour.step_inside,
        'dt': DiffBehaviour.internally,
        'dd': DiffBehaviour.internally,
        'figure': DiffBehaviour.internally,
        'figcaption': DiffBehaviour.internally,
        'div': DiffBehaviour.internally,
        'main': DiffBehaviour.internally,

        # ============== TEXT LEVEL =====================
        # https://www.w3.org/TR/html5/text-level-semantics.html#text-level-semantics
        'a': DiffBehaviour.internally,
        'em': DiffBehaviour.internally,
        'strong': DiffBehaviour.internally,
        'small':DiffBehaviour.internally,
        's': DiffBehaviour.internally,
        'cite': DiffBehaviour.internally,
        'q': DiffBehaviour.internally,
        'dfn': DiffBehaviour.internally,
        'data': DiffBehaviour.skip,
        'code': DiffBehaviour.internally,
        'samp': DiffBehaviour.internally,
        'sub': DiffBehaviour.internally,
        'sup': DiffBehaviour.internally,
        'i': DiffBehaviour.internally,
        'b': DiffBehaviour.internally,
        'u': DiffBehaviour.internally,
        'mark': DiffBehaviour.internally,
        'bdi': DiffBehaviour.internally,
        'bdo': DiffBehaviour.internally,
        'span': DiffBehaviour.internally,

        # line-breaks are placeholders tag without content inside
        'br': DiffBehaviour.as_block,
        'wbr': DiffBehaviour.as_block,

        # following tags might be diffed inside, but it was decided to avoid this because
        # internally diffed value can be misleading for humans or make tag unusable
        'abbr': DiffBehaviour.as_block,
        'time': DiffBehaviour.as_block,
        'kbd': DiffBehaviour.as_block,
        'var': DiffBehaviour.as_block,
        'ruby': DiffBehaviour.as_block,

        # rb, rt, rtc, rp omitted because are contents of ruby treated as block

        # ================= EMBEDDED ====================
        'img': DiffBehaviour.as_block,
        'iframe': DiffBehaviour.as_block,
        'embed': DiffBehaviour.as_block,
        'object': DiffBehaviour.as_block,
        'video': DiffBehaviour.as_block,
        'audio': DiffBehaviour.as_block,
        'svg': DiffBehaviour.as_block,
        'math': DiffBehaviour.as_block,

        # diffing maps internally is complex task and not well designed, currently not supported
        'map': DiffBehaviour.as_block,

        # param, source, track omitted, can exist only in other embedded which are diffed as block

        # ================= TABULAR =====================
        'table': DiffBehaviour.step_inside,
        'caption': DiffBehaviour.internally,
        'colgroup': DiffBehaviour.skip,
        # col is inside skipped colgroup
        'tbody': DiffBehaviour.step_inside,
        'thead': DiffBehaviour.step_inside,
        'tfoot': DiffBehaviour.step_inside,
        'tr': DiffBehaviour.step_inside,
        'td': DiffBehaviour.internally,
        'th': DiffBehaviour.internally,

        # =================== FORMS =====================
        'form': DiffBehaviour.internally,
        'label': DiffBehaviour.internally,
        'input': DiffBehaviour.as_block,
        'button': DiffBehaviour.as_block,
        'select': DiffBehaviour.as_block,
        'datalist': None,  # not supported
        'textarea': DiffBehaviour.as_block,
        'keygen': DiffBehaviour.as_block,
        'output': DiffBehaviour.internally,
        'progress': DiffBehaviour.as_block,
        'meter': DiffBehaviour.as_block,
        'fieldset': DiffBehaviour.internally,
        'legend': DiffBehaviour.internally,

        # optgroup and options omitted, because select is diffed as block

        # +================ SCRIPTING ====================
        'script': DiffBehaviour.skip,
        'noscript': DiffBehaviour.skip,
        'template': DiffBehaviour.skip
    }

    @classmethod
    def get_diff_type(cls, tag):
        """
        :param tag:
        :type tag: QName
        :rtype: DiffBehaviour,None
        :return:
        """
        if tag is None:
            # none means tree root parent (an abstract node, always diff it and can contain diff)
            return DiffBehaviour.internally

        return cls.DIFF_TYPE.get(tag.localname)
