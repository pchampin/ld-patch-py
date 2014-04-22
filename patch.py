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

from itertools import islice
from pyparsing import Group, Optional, Regex, Suppress, Word, ZeroOrMore
from rdflib import BNode, Literal, RDF, URIRef

COMMAND = Regex("A(d(d)?)?") ^ \
          Regex("D(e(l(e(t(e)?)?)?)?)?") ^ \
          Regex("C(l(e(a(r)?)?)?)?") ^ \
          Regex("R(e(p(l(a(c(e)?)?)?)?)?)?")
IRI = Regex(r"<[^> \t\r\n]*>") # TODO improve that
BNODE = Regex(r"_:[a-zA-Z_][-0-9a-zA-Z_.]*") # TODO improve that?
LITERAL = Group(Regex(r'"([^"]|\\")*"')
                + Optional( Suppress("@") + Regex("[-a-zA-Z]+"), None )
                + Optional( Suppress("^^") + IRI, None )) # TODO improve that?

IRI_INV = Group("-" + IRI)
NUMBER = Word("0123456789") # TODO improve that
INDEX = Group("[" + NUMBER + Suppress("]"))
PATH_ELT = (IRI ^ IRI_INV) + ZeroOrMore(INDEX)
INDICES = Group("[" + Optional(NUMBER) + Optional(":") + Optional(NUMBER)
                + Suppress("]"))
PATH = Group(PATH_ELT + ZeroOrMore(Suppress("/") + PATH_ELT)
             + Optional(INDICES))

LIST = Group("(" + ZeroOrMore(IRI ^ BNODE ^ LITERAL) + Suppress(")"))

ROW = (COMMAND
       + ("R" ^ IRI ^ BNODE ^ LITERAL)                 # subject
       + ("R" ^ PATH)                                  # predicate
       + Optional("R" ^ IRI ^ BNODE ^ LITERAL ^ LIST)  # object
       + Optional("R" ^ IRI ^ BNODE, None)             # graph-name
       + Suppress("."))


def is_iri(token):
    return isinstance(token, unicode) and token[0] == "<"

def is_bnode(token):
    return isinstance(token, unicode) and token[0] == "_"

def is_literal(token):
    return isinstance(token, list) and token[0][0] == '"'

def is_list(token):
    return isinstance(token, list) and token[0] == '('

def is_inv_iri(token):
    return isinstance(token, list) and token[0] == '-'

def is_indices(token):
    return isinstance(token, list) and token[0] == '['

def is_slice(token):
    return is_indices(token) and (len(token) != 2 or token[1] == ":")

def is_single_index(token):
    return is_indices(token) and len(token) == 2 and token[1] != ":"

def make_iri(token):
    assert is_iri(token), token
    return URIRef(token[1:-1])

def make_bnode(token):
    assert is_bnode(token), token
    return BNode(token[2:])

def make_literal(token):
    assert is_literal(token), token
    return Literal(
        token[0][1:-1],
        token[1],
        token[2] and URIRef(token[2][1:-1]) or None
        )

def make_slice(indices):
    if len(indices) == 1 or indices[1] == ":":
        imin = 0
    else:
        imin = int(indices[1])
    if len(indices) < 4:
        imax = None
    else:
        imax = indices[3]
    return imin, imax

def make_triple(start_node, path_elt, other_node):
    if is_inv_iri(path_elt):
        iother = 0
        trpl = [other_node, make_iri(path_elt[1]), start_node]
    else:
        assert is_iri(path_elt), path_elt
        iother = 2
        trpl = [start_node, make_iri(path_elt), other_node]
    return trpl, iother

def iter_targets(graph, start_node, path):
    if len(path) == 0:
        yield start_node
    else:
        query, iother = make_triple(start_node, path[0], None)
        for trpl in graph.triples(query):
            for target in iter_targets(graph, trpl[iother], path[1:]):
                yield target

def convert_single_indices(path):
    for i in range(len(path)):
        if is_single_index(path[i]):
            val = int(path[1][1])
            repl = (val
                    * [ u"<http://www.w3.org/1999/02/22-rdf-syntax-ns#rest>" ]
                    + [ u"<http://www.w3.org/1999/02/22-rdf-syntax-ns#first>" ]
                    )
            path[i:i+1] = repl

def clear_list(graph, prior_node, link, imin, imax):
    """Clear the list pointed from prior_node by link, between imin and imax.

    * imax can be None (meaning "until the end"),
    * imin and imax may be greater than the actual length of the list.

    Return src_node, link, dest_node where
    * src_node is the node on which a replacement list can be attached,
    * src_link is the link to use to attach the replacement list to src_node,
    * dest_node is the node to follow the replacement list.
    """
    assert imax is None  or  imin <= imax, (imin, imax)
    dest_node = None
    cur_node = src_node = prior_node
    src_link = link
    i_dest_node = -1
    while dest_node != RDF.nil and (imax is None or i_dest_node < imax):
        query, inext = make_triple(cur_node, link, None)
        candidates = [ t for t in islice(graph.triples(query), 1) ]
        dest_node = candidates and candidates[0][inext] or RDF.nil
        # if the list is ill-formed:
        # - several rdf:rest -> we consider only one
        # - no rdf:rest -> we consider that the node was RDF.nil
        i_dest_node += 1
        cur_node = dest_node
        link = u"<http://www.w3.org/1999/02/22-rdf-syntax-ns#rest>"
        if dest_node == RDF.nil:
            if candidates:
                graph.remove(candidates[0])
        else:
            if i_dest_node < imin:
                src_node = cur_node
                src_link = link
            elif imin <= i_dest_node and (imax is None or i_dest_node < imax):
                graph.remove(candidates[0])
                graph.remove((dest_node, RDF.first, None))
            else: # imax <= i_dest_node 
                graph.remove(candidates[0])
                
    return src_node, src_link, dest_node

class Patch(object):

    def __init__(self, stream, safe=True):
        self._stream = stream
        self._lineno = 0
        self._subject = None
        self._predicate = None
        self._object = None
        self._graphname = None
        self._graph = None
        self._safe = safe
        self._bnodemap = safe and {} or None

    def __iter__(self):
        for line in self._stream:
            self._lineno += 1
            if line == "\n" or line.strip()[0] == "#":
                continue
            yield ROW.parseString(line.decode("utf-8"), True).asList()

    def make_node(self, token, create=False):
        if is_iri(token):
            return make_iri(token)
        elif is_bnode(token):
            if not self._safe:
                return make_bnode(token)
            else:
                ret = self._bnodemap.get(token)
                if ret is None:
                    if not create:
                        raise PatchException("Unexpected fresh bnode %s"
                                             % token, self._lineno)
                    else:
                        ret = self._bnodemap[token] = BNode()
                return ret
        else:
            return make_literal(token)


    def apply_to(self, graph):
        for line in self:
            # line has structure [command, subject, predicate, object?, graph?]
            # where object may be absent, but graph would be None
            if len(line) < 4:
                raise PatchException("Tuple too short", self._lineno)
            if line[1] != "R":
                self._subject = line[1]
            if line[2] != "R":
                self._predicate = line[2]
            if line[3] != "R":
                self._object = line[3]

            if self._subject is None:
                raise PatchException("No subject to repeat",
                                     self._lineno)
            if self._predicate is None:
                raise PatchException("No predicate to repeat",
                                     self._lineno)
            endsWithIndices = is_indices(self._predicate[-1])
            if line[0][0] != "R":
                if endsWithIndices:
                    raise PatchException("Indices not supported by %s"
                                         % line[0], self._lineno)
                if is_list(self._object):
                    raise PatchException("List object not supported by %s"
                                         % line[0], self._lineno)
            convert_single_indices(self._predicate)

            if line[0][0] == "A":
                self._apply_add(line, graph)
            elif line[0][0] == "D":
                self._apply_del(line, graph)
            elif line[0][0] == "C":
                self._apply_clear(line, graph)
            else:
                assert line[0][0] == "R", line[0]
                if is_slice(self._predicate[-1]):
                    self._apply_repl_slice(line, graph)
                else:
                    self._apply_repl_triple(line, graph)

        return graph


    def _apply_add(self, line, graph):
        self._common_apply(line, graph)

        subj = self.make_node(self._subject)
        obj = self.make_node(self._object, True)
        targets = list(
            islice(iter_targets(self._graph, subj, self._predicate[:-1]), 2))
        if len(targets) > 1:
            raise PatchException("Ambiguous path", self._lineno)
        elif len(targets) == 0:
            raise PatchException("Inexisting path", self._lineno)
        trpl, _ = make_triple(targets[0], self._predicate[-1], obj)
        self._graph.add(trpl)

    def _apply_del(self, line, graph):
        self._common_apply(line, graph)

        subj = self.make_node(self._subject)
        obj = self.make_node(self._object)
        targets = list(
            islice(iter_targets(self._graph, subj, self._predicate[:-1]), 2))
        if len(targets) > 1:
            raise PatchException("Ambiguous path", self._lineno)
        elif len(targets) == 0:
            # ignore if no candidates
            return            
        trpl, _ = make_triple(targets[0], self._predicate[-1], obj)
        self._graph.remove(trpl)

    def _apply_clear(self, line, graph):
        if not (4 <= len(line) <= 5):
            raise PatchException("Wrong number of arguments for C",
                                 self._lineno)
        subj = self.make_node(self._subject)
        self._object = None
        self._update_graph(line[3], graph)
        targets = list(
            islice(iter_targets(self._graph, subj, self._predicate[:-1]), 2))
        if len(targets) > 1:
            raise PatchException("Ambiguous path", self._lineno)
        elif len(targets) == 0:
            # ignore if no candidates
            return            
        trpl, _ = make_triple(targets[0], self._predicate[-1], None)
        self._graph.remove(trpl)

    def _apply_repl_triple(self, line, graph):
        self._common_apply(line, graph)
        if is_list(self._object):
            raise PatchException("List object requires a slice predicate",
                                 self._lineno)
        subj = self.make_node(self._subject)
        obj = self.make_node(self._object)
        targets = list(
            islice(iter_targets(self._graph, subj, self._predicate[:-1]), 2))
        if len(targets) > 1:
            raise PatchException("Ambiguous path", self._lineno)
        elif len(targets) == 0:
            raise PatchException("Inexisting path", self._lineno)

        elt = self._predicate[-1]
        trpl, iother = make_triple(targets[0], self._predicate[-1], obj)
        query = list(trpl)
        query[iother] = None
        candidates = list(islice(self._graph.triples(query), 2))
        if len(candidates) > 2:
            raise PatchException("Can not replace multi-valued property",
                                 self._lineno)
        elif len(candidates) == 1:
            self._graph.remove(candidates[0])
        self._graph.add(trpl)

    def _apply_repl_slice(self, line, graph):
        self._common_apply(line, graph)
        if not is_list(self._object):
            raise PatchException("Slice predicate requires a list object",
                                 self._lineno)
        subj = self.make_node(self._subject)
        targets = list(
            islice(iter_targets(self._graph, subj, self._predicate[:-2]), 2))
        if len(targets) > 1:
            raise PatchException("Ambiguous path", self._lineno)
        elif len(targets) == 0:
            raise PatchException("Inexisting path", self._lineno)
        prior_node = targets[0]

        imin, imax = make_slice(self._predicate[-1])
        src_node, link, dest_node = clear_list(self._graph, prior_node,
                                               self._predicate[-2], imin, imax)
        previous = src_node
        for val in self._object[1:]:
            val = self.make_node(val)
            bnode = BNode()
            self._graph.add((bnode, RDF.first, val))
            trpl, _ = make_triple(previous, link, bnode)
            self._graph.add(trpl)
            previous = bnode
            link = u"<http://www.w3.org/1999/02/22-rdf-syntax-ns#rest>"
        trpl, _ = make_triple(previous, link, dest_node)
        self._graph.add(trpl)


    def _common_apply(self, line, graph):
        """Everything that is common to all operations but C"""
        if len(line) != 5:
            raise PatchException("Wrong number of arguments for %s" % line[0],
                                 self._lineno)
        if self._object is None:
            raise PatchException("No object to repeat", self._lineno)
        self._update_graph(line[4], graph)

    def _update_graph(self, name_in_line, graph):
        if name_in_line is None:
            self._graphname = None
            self._graph = graph
        elif name_in_line == "R":
            if self._graphname is None:
                raise PatchException("No graph name to repeat", self._lineno)
        else:
            self._graphname = name_in_line
            self._graph = Graph(graph.store, self.make_node(name_in_line))

            


class PatchException(Exception):
    def __init__(self, msg, lineno):
        Exception.__init__(self, msg)
        self.lineno = lineno

    def __str__(self):
        return "%s at line %s" % (self.message, self.lineno)


if __name__ == "__main__":
    import sys
    from rdflib import Graph
    if len(sys.argv) != 2 or "--help" in sys.argv:
        print "usage: %s <turtle-file" % sys.argv[0]
        print "  reads an rdf-patch on stdin, applies it to <turtle-file>,"
        print "  and outputs the resulting graph in turtle"
        exit(-1)

    g = Graph()
    g.load(sys.argv[1], format="turtle")
    p = Patch(sys.stdin)
    p.apply_to(g)
    print g.serialize(format="turtle")

