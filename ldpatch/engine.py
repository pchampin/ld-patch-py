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
"""

from collections import namedtuple

from rdflib import BNode, RDF, URIRef as IRI, Variable
from rdflib.exceptions import UniquenessError
from rfc3987 import parse as parse_iri

InvIRI = namedtuple("InvIRI", ["iri"])

_PathConstraintBase = namedtuple("PathConstraint", ["path", "value"])
class PathConstraint(_PathConstraintBase):
    def __new__(cls, path, value=None):
        return _PathConstraintBase.__new__(cls, path, value)

Slice = namedtuple("Slice", ["idx1", "idx2"])
""" A slice of indexes in a list.

    idx1 == None means "after the end" (idx2 will then be unspecified)
    idx2 == None means "until the end"
"""

class _UnicityConstraintSingleton(object):
    def __repr_(self):
        return "UNICITY_CONSTRAINT"
UNICITY_CONSTRAINT = _UnicityConstraintSingleton()


def _get_last_node(graph, lst):
    """
    Find the last node of a non-empty list
    """
    assert lst != RDF.nil
    last = lst
    graph_value = graph.value
    while True:
        nxt = graph_value(last, RDF.rest, any=False)
        if nxt is None:
            raise MalformedListException()
        if nxt == RDF.nil:
            break
        last = nxt
    return last


class PatchEngine(object):
    """
    An object actually doing the ldpatch
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
        if typelt is Variable:
            ret = self._variables.get(element)
            if ret is not None:
                return ret
            else:
                raise UnboundVariableError(str(element))
        elif typelt is BNode:
            ret = self._bnodes.get(element)
            if ret is None:
                ret = self._bnodes[element] = BNode()
        elif typelt is IRI:
            # invalid IRIs can result from \uxxxx or \Uxxxxxxxx encoding ;
            # so this is not stricly speaking a ParserError,
            # but rather a semantic error, hence its processing here
            try:
                parse_iri(element, rule="IRI")
            except ValueError, ex:
                raise PatchEvalError(ex.message)
            ret = element
        else:
            ret = element
        return ret

    def do_path_step(self, nodeset, pathelt):
        typelt = type(pathelt)
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
                value = self.get_node(value)
            return (value in nodeset)

    def updatelist_empty(self, udl_graph, subject, predicate, slice, udl_head):
        if udl_head == RDF.nil:
            return # replace empty list by empty list == noop
        idx1, idx2 = slice.idx1, slice.idx2
        if idx1 is not None and idx1 > 0:
            raise OutOfBoundUpdateListException()
        if idx2 is not None and idx2 > 0:
            raise OutOfBoundUpdateListException()
        if udl_head != RDF.nil:
            self.add(udl_graph)
            new_lst = self.get_node(udl_head)
            self._graph.remove(subject, predicate, RDF.nil)
            self._graph.add(subject, predicate, new_lst)

    def replace_listnode(self, old_node, new_node):
        graph = self._graph
        graph_add = graph.add
        graph_rem = graph.remove
        for _, p, o in graph.triples((old_node, None, None)):
            # we do not change RDF.first and RDF.rest,
            # because old_node might still be part of the updated list
            # (when *inserting* elements in a list)
            if p != RDF.first and p != RDF.rest:
                graph_rem((old_node, p, o))
                graph_add((new_node, p, o))
        for s, p, _ in graph.triples((None, None, old_node)):
            graph_rem((s, p, old_node))
            graph_add((s, p, new_node))


    # ldpatch commands

    def prefix(self, prefix, iri):
        self._namespaces[prefix] = iri

    def bind(self, variable, value, path):
        assert isinstance(variable, Variable)
        path = list(path)

        nodeset = {self.get_node(value)}
        for step in path:
            nodeset = self.do_path_step(nodeset, step)
        if len(nodeset) != 1:
            raise NoUniqueMatch(nodeset)
        self._variables[variable] =  iter(nodeset).next()

    def add(self, add_graph):
        get_node = self.get_node
        graph_add = self._graph.add
        for subject, predicate, object in add_graph:
            subject = get_node(subject)
            predicate = get_node(predicate)
            object = get_node(object)
            graph_add((subject, predicate, object))

    def delete(self, del_graph):
        get_node = self.get_node
        graph_rem = self._graph.remove
        for subject, predicate, object in del_graph:
            subject = get_node(subject)
            predicate = get_node(predicate)
            object= get_node(object)
            graph_rem((subject, predicate, object))

    def updatelist(self, udl_graph, subject, predicate, slice, udl_head):
        try:
            graph_value = self._graph.value
            subject = self.get_node(subject)
            predicate = self.get_node(predicate)
            try:
                old_lst = graph_value(subject, predicate, any=True)
            except UniquenessError, ex:
                raise
            if old_lst is None:
                raise NoSuchListException()

            if old_lst == RDF.nil:
                self.updatelist_empty(udl_graph, subject, predicate, slice, udl_head)
                return

            idx1, idx2 = slice.idx1, slice.idx2

            # look for the left "anchor" for the new list
            left_anchor = None
            right_anchor = None
            pred = None
            to_clean = []
            if idx1 is None:
                assert idx2 is None # should be controlled by the parser
                left_anchor = RDF.nil
            else:
                left_anchor = old_lst
                i = 0
                while idx1 is None or i < idx1:
                    if left_anchor == RDF.nil:
                        raise OutOfBoundUpdateListException()
                    pred = left_anchor
                    left_anchor = graph_value(left_anchor, RDF.rest, any=False)
                    if left_anchor is None:
                        raise MalformedListException()
                    i += 1
                if left_anchor == RDF.nil:
                    if idx2 is not None and idx2 > idx1:
                        raise OutOfBoundUpdateListException()

                # look for the right "anchor" for the new list,
                # and mark all intermediate nodes for cleaning
                # NB: idx2 can be None, meaning "until the end"
                right_anchor = left_anchor
                while (i < idx2 or idx2 is None) and right_anchor != RDF.nil:
                    to_clean.append(right_anchor)
                    right_anchor = graph_value(right_anchor, RDF.rest, any=False)
                    if right_anchor is None:
                        raise MalformedListException()
                    i += 1
            assert left_anchor is not None

            # add new list in the graph and link it adequately
            assert udl_head != RDF.nil or len(udl_graph) == 0
            self.add(udl_graph)
            new_lst = self.get_node(udl_head)
            if left_anchor == RDF.nil:
                last_old = pred or _get_last_node(self._graph, old_lst)
                self._graph.set((last_old, RDF.rest, new_lst))
                assert len(to_clean) == 0
            else:
                if new_lst != RDF.nil:
                    self.replace_listnode(left_anchor, new_lst)
                    last_new = _get_last_node(self._graph, new_lst)
                    self._graph.set((last_new, RDF.rest, right_anchor))
                elif left_anchor != right_anchor:
                    self.replace_listnode(left_anchor, right_anchor)
                graph_remove = self._graph.remove
                for i in to_clean:
                    graph_remove((i, None, None))

        except UniquenessError, ex:
            raise MalformedListException(ex.msg)



class PatchEvalError(Exception):
    pass

class NoUniqueMatch(PatchEvalError):
    def __init__(self, nodeset):
        Exception.__init__(self, "{!r}".format(nodeset))
        self.nodeset = nodeset

class UnboundVariableError(PatchEvalError):
    pass

class UndefinedPrefixError(PatchEvalError):
    pass

class NoSuchListException(PatchEvalError):
    pass

class MalformedListException(PatchEvalError):
    pass

class OutOfBoundUpdateListException(PatchEvalError):
    pass
