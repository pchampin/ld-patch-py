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


    # ldpatch commands

    def prefix(self, prefix, iri):
        self._namespaces[prefix] = iri

    def bind(self, variable, value, path=[]):
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
        graph = self._graph
        graph_rem = graph.remove
        for subject, predicate, object in del_graph:
            subject = get_node(subject)
            predicate = get_node(predicate)
            object= get_node(object)
            triple = (subject, predicate, object)
            if triple not in graph:
                raise NoSuchTriple(triple)
            graph_rem(triple)

    def updatelist(self, udl_graph, subject, predicate, slice, udl_head):
        try:
            target = self._graph
            spre = self.get_node(subject)
            ppre = self.get_node(predicate)
            opre = target.value(spre, ppre, any=False)
            if opre is None:
                raise NoSuchListException()
            imin, imax = slice.idx1, slice.idx2

            i = 0
            while (imin is not None and i < imin) \
               or (imin is None and opre != RDF.nil):
                spre, ppre, opre = \
                    opre, RDF.rest, target.value(opre, RDF.rest, any=False)
                if opre is None:
                    raise MalformedListException("TODO message 1")
                i += 1
            print "===", "PRE", spre, ppre, opre, target.value(spre, RDF.first)

            spost, ppost, opost = spre, ppre, opre
            while (imax is not None and i < imax) \
               or (imax is None and opost != RDF.nil):
                target.remove((spost, ppost, opost))
                elt = target.value(opost, RDF.first, any=False)
                if elt is None:
                    raise MalformedListException("TODO message 2")
                # TODO cut elt if bnode
                print "===", "DEL", elt
                target.remove((opost, RDF.first, elt))
                spost, ppost, opost = \
                    opost, RDF.rest, target.value(opost, RDF.rest, any=False)
                if opost is None:
                    raise MalformedListException("TODO message 3 ")
                i += 1
            print "===", "POST", spost, ppost, opost, target.value(spost, RDF.first)

            target.remove((spre, ppre, opre))
            target.remove((spost, ppost, opost))

            if udl_head == RDF.nil:
                target.add((spre, ppre, opost))
            else:
                self.add(udl_graph)
                fst = self.get_node(udl_head)
                lst = _get_last_node(target, fst)
                target.add((spre, ppre, fst))
                target.set((lst, RDF.rest, opost))

        except UniquenessError, ex:
            raise MalformedListException(ex.msg)



class PatchEvalError(Exception):
    pass

class NoUniqueMatch(PatchEvalError):
    def __init__(self, nodeset):
        Exception.__init__(self, "{!r}".format(nodeset))
        self.nodeset = nodeset

class NoSuchTriple(PatchEvalError):
    def __init__(self, triple):
        Exception.__init__(self, "{} {} {}".format(*triple))
        self.triple = triple

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
