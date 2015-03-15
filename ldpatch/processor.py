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
I implement a processor executing an LD-Patch.
"""

# pylint: disable=W0142,R0801

from collections import namedtuple

from rdflib import BNode, RDF, URIRef as IRI, Variable
from rdflib.exceptions import UniquenessError
from rfc3987 import parse as parse_iri

InvIRI = namedtuple("InvIRI", ["iri"])

_PathConstraintBase = namedtuple("PathConstraint", ["path", "value"])
class PathConstraint(_PathConstraintBase):
    """A constraint appearing in a Path Expression"""
    #pylint: disable=R0903
    def __new__(cls, path, value=None):
        return _PathConstraintBase.__new__(cls, path, value)

Slice = namedtuple("Slice", ["idx1", "idx2"])
""" A slice of indexes in a list.

    idx1 == None means "after the end" (idx2 will then be unspecified)
    idx2 == None means "until the end"
"""

class _UnicityConstraintSingleton(object):
    """A singleton class for representing the unicity constraint
    in Path Expressions"""
    #pylint: disable=R0903
    def __repr__(self):
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
        try:
            nxt = graph_value(last, RDF.rest, any=False)
        except UniquenessError:
            nxt = None
        if nxt is None:
            raise ValueError("Malformed list passed to UpdateList")
        if nxt == RDF.nil:
            break
        last = nxt
    return last

def _get_list_length(graph, lst):
    """
    Find the length of an RDF list
    """
    graph_value = graph.value
    ret = 0
    while lst != RDF.nil:
        try:
            lst = graph_value(lst, RDF.rest, any=False)
        except UniquenessError:
            lst = None
        if lst is None:
            raise MalformedListError()
        ret += 1
    return ret


class PatchProcessor(object):
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
                parse_iri(unicode(element), rule="IRI")
            except ValueError, ex:
                raise PatchEvalError(ex.message)
            ret = element
        else:
            ret = element
        return ret

    def do_path_step(self, nodeset, pathelt):
        """Process one step of a Path Expression"""
        typelt = type(pathelt)
        if typelt is IRI:
            return { trpl[2]
                     for subj in nodeset
                     for trpl in self._graph.triples((subj, pathelt, None))
                   }
        elif typelt is InvIRI:
            return { trpl[0]
                     for obj in nodeset
                     for trpl in self._graph.triples((None, pathelt.iri, obj))
                   }
        elif typelt is int:
            ret = set(nodeset)
            for _ in range(pathelt):
                ret = self.do_path_step(ret, RDF.rest)
            ret = self.do_path_step(ret, RDF.first)
            return ret
        elif typelt is PathConstraint:
            return { i for i in nodeset if self.test_path_constraint(i, pathelt) }
        elif pathelt is UNICITY_CONSTRAINT:
            if len(nodeset) != 1:
                raise NoUniqueMatchError(None, pathelt, nodeset)
            return nodeset
        else:
            raise TypeError("Unrecognized path element {!r}".format(pathelt))

    def test_path_constraint(self, node, constraint):
        """Check a constraint in a Path Expression"""
        nodeset = {node}
        try:
            for pathelt in constraint.path:
                nodeset = self.do_path_step(nodeset, pathelt)
                if len(nodeset) == 0:
                    return False
        except NoUniqueMatchError:
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
            return (value in nodeset) #pylint: disable=C0325


    # ldpatch commands

    def prefix(self, prefix, iri):
        """Process a Prefix command"""
        self._namespaces[prefix] = iri

    def bind(self, variable, value, path=()):
        """Process a Bind command"""
        assert isinstance(variable, Variable)
        path = list(path)

        nodeset = {self.get_node(value)}
        try:
            for step in path:
                nodeset = self.do_path_step(nodeset, step)
        except NoUniqueMatchError, ex:
            ex.variable = variable
            raise
        if len(nodeset) != 1:
            raise NoUniqueMatchError(variable, "end", nodeset)
        self._variables[variable] =  iter(nodeset).next()

    def add(self, add_graph, addnew=False):
        """Process an Add or AnnNew command"""
        get_node = self.get_node
        graph = self._graph
        graph_add = graph.add
        for subject, predicate, objct in add_graph:
            subject = get_node(subject)
            predicate = get_node(predicate)
            objct = get_node(objct)
            triple = (subject, predicate, objct)
            if addnew and triple in graph:
                raise AddNewError(triple)
            graph_add(triple)

    def delete(self, del_graph, delex=False):
        """Process a Delete or DeleteExisting command"""
        get_node = self.get_node
        graph = self._graph
        graph_rem = graph.remove
        for subject, predicate, objct in del_graph:
            subject = get_node(subject)
            predicate = get_node(predicate)
            objct= get_node(objct)
            triple = (subject, predicate, objct)
            if delex and triple not in graph:
                raise DeleteExistingError(triple)
            graph_rem(triple)

    def cut(self, var, _override=None):
        """Process a Cut command"""
        if _override:
            start = _override
        else:
            start = self.get_node(var)
        if type(start) is not BNode:
            raise CutExpectsBnodeError()

        did_something = False
        get_triples = self._graph.triples
        rem_triple = self._graph.remove
        queue = [start,]
        while queue:
            bnode = queue.pop()
            for trpl in get_triples((bnode, None, None)):
                did_something = True
                rem_triple(trpl)
                if type(trpl[2]) is BNode:
                    queue.append(trpl[2])
        for trpl in get_triples((None, None, start)):
            did_something = True
            rem_triple(trpl)
        if not did_something:
            raise CurRemovedNothing()


    def updatelist(self, udl_graph, subject, predicate, aslice, udl_head):
        """Process an UpdateList command"""
        #pylint: disable=R0912,R0913,R0914,R0915
        try:
            target = self._graph
            spre = self.get_node(subject)
            ppre = self.get_node(predicate)
            try:
                opre = target.value(spre, ppre, any=False)
            except UniquenessError:
                opre = None
            if opre is None:
                raise NoUniqueMatchError("UpdateList", ppre, opre)
            imin, imax = aslice.idx1, aslice.idx2
            length = None
            if imin is not None and imin < 0:
                length = _get_list_length(target, opre)
                imin += length
                if imin < 0:
                    raise OutOfBoundUpdateListError("imin too small")
            if imax is not None and imax < 0:
                if length is None:
                    length = _get_list_length(target, opre)
                imax += length
                if imax < 0:
                    raise OutOfBoundUpdateListError("imax too small")

            i = 0
            while (imin is not None and i < imin) \
               or (imin is None and opre != RDF.nil):
                if opre == RDF.nil:
                    raise OutOfBoundUpdateListError(
                        "imin (%s) is greater than the length (%s)" % (imin, i))
                try:
                    spre, ppre, opre = \
                        opre, RDF.rest, target.value(opre, RDF.rest, any=False)
                except UniquenessError:
                    opre = None
                if opre is None:
                    raise MalformedListError("Item %s has not exactly one rdf:rest" % i)
                i += 1

            spost, ppost, opost = spre, ppre, opre
            while (imax is not None and i < imax) \
               or (imax is None and opost != RDF.nil):
                if opost == RDF.nil:
                    raise OutOfBoundUpdateListError(
                        "imax (%s) is greater than the length (%s)" % (imin, i))
                target.remove((spost, ppost, opost))
                try:
                    elt = target.value(opost, RDF.first, any=False)
                except UniquenessError:
                    elt = None
                if elt is None:
                    raise MalformedListError("Item %s has not exactly one rdf:first" % i)
                if type(elt) is BNode:
                    self.cut(None, elt)
                target.remove((opost, RDF.first, elt))
                try:
                    spost, ppost, opost = \
                        opost, RDF.rest, target.value(opost, RDF.rest, any=False)
                except UniquenessError:
                    opost = None
                if opost is None:
                    raise MalformedListError("Item %s has not exactly one rdf:rest" % i)
                i += 1

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
            raise MalformedListError(ex.msg)



class PatchEvalError(Exception):
    """Subclass of all errors generated by an LD Patch processor"""
    statusCode = 422


class AddNewError(PatchEvalError):
    """Error raised by AddNew if a triple already exists"""
    def __init__(self, triple):
        PatchEvalError.__init__(self, "{} {} {}".format(*triple))
        self.triple = triple

class CutExpectsBnodeError(PatchEvalError):
    """Error raised when Cut is applied to a node which is not a blank node"""
    pass

class CurRemovedNothing(PatchEvalError):
    """Error raised when Cut is applied to a node with no arc"""
    pass

class DeleteExistingError(PatchEvalError):
    """Error raised by DeleteExisting if a triple does not exist"""
    def __init__(self, triple):
        PatchEvalError.__init__(self, "{} {} {}".format(*triple))
        self.triple = triple

class MalformedListError(PatchEvalError):
    """Error raised when UpdateList is applied to a malformed list"""
    pass

class NoUniqueMatchError(PatchEvalError):
    """Error raised when a Path Expression does not match exactly one node"""
    def __init__(self, variable, step, nodeset):
        PatchEvalError.__init__(self)
        self.variable = variable
        self.step = step
        self.nodeset = nodeset

    def __str__(self):
        return "NoUniqueMatch for ?{} at {} (result: {})".format(
            self.variable, self.step, self.nodeset)

class OutOfBoundUpdateListError(PatchEvalError):
    """Error raised when the slice in UpdateList exceeds the length of the list"""
    pass

class UnboundVariableError(PatchEvalError):
    """Error raised when using an unbound variable"""
    statusCode = 400

class UndefinedPrefixError(PatchEvalError):
    """Error raised when using an undefined prefix"""
    statusCode = 400

