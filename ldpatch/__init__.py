# -*- coding: utf-8 -*-

#    This file is part of RDF-PATCH
#    Copyright (C) 2013 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Universite de Lyon <http://www.universite-lyon.fr>
#
#    RDF-PATCH is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    RDF-PATCH is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with RDF-PATCH.  If not, see <http://www.gnu.org/licenses/>.

from os.path import abspath
from urllib import pathname2url

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
        from .syntax import Parser
    else:
        raise ValueError("Unknown LD-Patch syntax {}".format())

    if baseiri is None:
        if hasattr(patch, "geturl"):
            baseiri = patch.geturl()
        elif hasattr(patch, "name"):
            baseiri = "file://" + pathname2url(abspath(patch.name))
        else:
            raise ValueError("Can not guess base-uri")

    if hasattr(patch, "read"):
        patch = patch.read()

    from .processor import PatchProcessor
    Parser(PatchProcessor(graph, init_ns, init_var), baseiri).parseString(patch)
