# -*- coding: utf-8 -*-

#    This file is part of LD-PATCH-PY
#    Copyright (C) 2013-2015 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Universite de Lyon <http://www.universite-lyon.fr>
#
#    LD-PATCH-PY is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    LD-PATCH-PY is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with LD-PATCH-PY.  If not, see <http://www.gnu.org/licenses/>.
"""
Python implementation of LD Patch.
"""
# pylint: disable=W0622,R0913

from os.path import abspath
from urllib import pathname2url

__version__ = "0.9"

def apply(patch, graph, baseiri=None, init_ns=None, init_var=None, syntax="default"):
    """
    I parse `patch` (either a file-like or a string), and apply it to `graph`.

    NB: if patch is a string, baseiri must be provided

    Other parameters:
    * `init_ns`: initial namespace binding
    * `init_var`: initial variables binding
    * `syntax`: concrete syntax used in `patch`
    """
    if syntax == "default":
        from ldpatch.syntax import Parser
    else:
        raise ValueError("Unknown LD-Patch syntax {}".format(syntax))

    if baseiri is None:
        if hasattr(patch, "geturl"):
            baseiri = patch.geturl()
        elif hasattr(patch, "name"):
            baseiri = "file://" + pathname2url(abspath(patch.name))
        else:
            raise ValueError("Can not guess base-uri")

    if hasattr(patch, "read"):
        patch = patch.read()

    from ldpatch.processor import PatchProcessor
    Parser(PatchProcessor(graph, init_ns, init_var), baseiri).parseString(patch)
