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

"""
I implement an engine executing an LD-Patch.

Design note
-----------

This implementation is not limited to the abstract syntax of LD-Patch,
it extends it with a Prefix command (for binding a prefix to a namespace)
and supports PrefixedNames wherever IRIs are expected.

While this could be handled by concrete syntax parsers,
(and may be should for the sake of purity),
it seems like a better idea to factorize it here,
as all concrete syntax will probably have to rely on such a mechanism.

TODO: another approach would be to expect parsers to use expand_pname,
and to only provide IRIs. Might be cleaner?
"""

from collections import namedtuple

from rdflib import BNode, Literal, RDF, URIRef as IRI, Variable


_PrefixedNameBase = namedtuple("PrefixedName", ["prefix", "suffix"])
class PrefixedName (_PrefixedNameBase):
    def __new__(cls, prefix, suffix=""):
        return _PrefixedNameBase.__new__(cls, prefix, suffix)

InvIRI = namedtuple("InvIRI", ["iri"])

_PathConstraintBase = namedtuple("PathConstraint", ["path", "value"])
class PathConstraint(_PathConstraintBase):
    def __new__(cls, path, value=None):
        return _PathConstraintBase.__new__(cls, path, value)

_SliceBase = namedtuple("Slice", ["idx1", "idx2"])
class Slice(_SliceBase):
    """A slice of indexes in a list.

    idx1 == None means "after the end" (idx2 will then be unspecified)
    idx2 == None means "until the end"
    """
    def __new__(cls, idx1, sep=None, idx2=None):
        if sep is None:
            assert idx1 is not None  and  idx2 is None
            idx2 = idx1 + 1
        return _SliceBase.__new__(cls, idx1, idx2)

class _UnicityConstraintSingleton(object):
    def __repr__(self):
        return "UNICITY_CONSTRAINT"
UNICITY_CONSTRAINT = _UnicityConstraintSingleton()



class PatchEngine(object):
    """
    An object actually doing the patch
    """

    def __init__(self, graph, init_ns=None, init_vars=None):
        self._graph = graph
        self._namespaces = {}
        self._variables = {}
        self._bnodes = {}
        if init_ns is not None:
            self._namespaces.update(init_ns)
        if init_vars is not None:
            self._variables.update(init_vars)

    # helper methods

    def expand_pname(self, prefix, suffix=""):
        """
        Convert prefixed name to IRI.
        """
        iriprefix = self._namespaces.get(prefix)
        if iriprefix is None:
            raise UndefinedPrefixError(
                "{}:{}".format(prefix, suffix))
        return IRI(iriprefix + suffix)

    def get_node(self, element):
        """
        Convert variables and bnodes, and return anything else unchanged.
        """
        typelt = type(element)
        if typelt is PrefixedName:
            return self.expand_pname(*element)
        elif typelt is Variable:
            ret = self._variables.get(element)
            if ret is not None:
                return ret
            else:
                raise UnboundVariableError(str(element))
        elif typelt is BNode:
            ret = self._bnodes.get(element)
            if ret is None:
                ret = self._bnodes[element] = BNode()
        else:
            ret = element
        return ret

    def do_path_step(self, nodeset, pathelt):
        typelt = type(pathelt)
        if typelt is PrefixedName:
            pathelt = self.expand_pname(*pathelt)
            typelt = IRI
        if typelt is IRI:
            return {
                trpl[2]
                    for subj in nodeset
                    for trpl in self._graph.triples((subj, pathelt, None))
            }
        elif typelt is InvIRI:
            return {
                trpl[0]
                    for obj in nodeset
                    for trpl in self._graph.triples((None, pathelt.iri, obj))
            }
        elif typelt is int:
            ret = set(nodeset)
            for i in range(pathelt):
                ret = self.do_path_step(ret, RDF.rest)
            ret = self.do_path_step(ret, RDF.first)
            return ret
        elif typelt is PathConstraint:
            return { i for i in nodeset if self.test_path_constraint(i, pathelt) }
        elif pathelt is UNICITY_CONSTRAINT:
            if len(nodeset) != 1:
                raise NoUniqueMatch(nodeset)
            return nodeset
        else:
            raise TypeError("Unrecognized path element {!r}".format(pathelt))


    def test_path_constraint(self, node, constraint):
        nodeset = {node}
        try:
            for pathelt in constraint.path:
                nodeset = self.do_path_step(nodeset, pathelt)
                if len(nodeset) == 0:
                    return False
        except NoUniqueMatch:
            return False

        if constraint.value is None:
            return True # empty nodesets have already returned 0 above
        else:
            value = constraint.value
            typval = type(value)
            if typval == Variable:
                value = self.get_node(value)
            elif typval == BNode:
                value = self.get_bnode(value)
            return (value in nodeset)

    def _generate_list(self, lst, nil=RDF.nil):
        graph_add = self._graph.add
        curnode= nil
        reversed_items = [ self.get_node(i) for i in reversed(lst) ]
        for i in reversed_items:
            oldnode = curnode
            curnode= BNode()
            graph_add((curnode, RDF.rest, oldnode))
            graph_add((curnode, RDF.first, i))
        return curnode


    # patch commands

    def prefix(self, prefix, iri):
        self._namespaces[prefix] = iri

    def bind(self, variable, path):
        assert isinstance(variable, Variable)
        path = list(path)
        assert len(path) >= 1

        nodeset = {self.get_node(path[0])}
        for step in path[1:]:
            nodeset = self.do_path_step(nodeset, step)
        if len(nodeset) != 1:
            raise NoUniqueMatch(nodeset)
        self._variables[variable] =  iter(nodeset).next()

    def add(self, subject, predicate, object):
        subject = self.get_node(subject)
        predicate = self.get_node(predicate)
        if type(object) is list:
            object = self._generate_list(object)
        else:
            object = self.get_node(object)
        self._graph.add((subject, predicate, object))

    def delete(self, subject, predicate, object):
        subject = self.get_node(subject)
        predicate = self.get_node(predicate)
        object= self.get_node(object)
        self._graph.remove((subject, predicate, object))

    def replace(self, subject, predicate, slice, lst):
        graph_value = self._graph.value
        subject = self.get_node(subject)
        predicate = self.get_node(predicate)

        current = graph_value(subject, predicate)
        if current is None:
            raise NoSuchListException()

        idx1, idx2 = slice.idx1, slice.idx2

        # look for the left "anchor" for the new list
        left_anchor = subject
        i = 0
        if idx1 is not None:
            while i < idx1:
                left_anchor = current
                current = graph_value(current, RDF.rest)
                if current is None:
                    raise MalformedListException()
                if current == RDF.nil:
                    raise OutOfBoundReplaceException()
                i += 1
        else:
            while current != RDF.nil:
                left_anchor = current
                current = graph_value(current, RDF.rest)
                if current is None:
                    raise MalformedListException()

        # look for the right "anchor" for the new list,
        # and mark all intermediate nodes for cleaning
        # NB: idx2 can be None, meaning "until the end"
        clean_list = []
        while (i < idx2 or idx2 is None) and current != RDF.nil:
            clean_list.append(current)
            current = graph_value(current, RDF.rest)
            if current is None:
                raise MalformedListException()
            i += 1
        right_anchor = current

        # replace old list by new list
        new_list = self._generate_list(lst, right_anchor)
        if left_anchor is not subject:
            predicate = RDF.rest
        self._graph.set((left_anchor, predicate, new_list))
        graph_remove = self._graph.remove
        for i in clean_list:
            graph_remove((i, None, None))





class NoUniqueMatch(Exception):
    def __init__(self, nodeset):
        Exception.__init__(self, "{!r}".format(nodeset))
        self.nodeset = nodeset

class UnboundVariableError(Exception):
    pass

class UndefinedPrefixError(Exception):
    pass

class NoSuchListException(Exception):
    pass

class MalformedListException(Exception):
    pass

class OutOfBoundReplaceException(Exception):
    pass