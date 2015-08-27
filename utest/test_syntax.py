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

from __future__ import unicode_literals

from nose.tools import assert_raises, assert_list_equal, eq_
from unittest import skip
from rdflib import BNode as B, Graph, Literal, Namespace, RDF, URIRef, Variable as V, XSD
from rdflib.collection import Collection
from rdflib.compare import isomorphic

from ldpatch.processor import InvIRI, PathConstraint, Slice, UNICITY_CONSTRAINT
from ldpatch.syntax import Parser, ParserError

EX = Namespace("http://ex.co/")


def eqg_(got, expected):
    exp = Graph()
    for i in expected:
        exp.add(i)
    assert isomorphic(got, exp), \
        "Got graph:\n\n" + got.serialize(format="turtle")
    
def _s(graph):
    return graph.serialize(format="n3")
    
class DummyProcessor(object):
    def __init__(self):
        self.operations = []

    def pop(self):
        return self.operations.pop()

    def is_empty(self):
        return len(self.operations) == 0

    def expand_pname(self, prefix, suffix=""):
        return URIRef(EX[suffix])

    def prefix(self, prefix, iri):
        self.operations.append(("prefix", prefix, iri))

    def bind(self, variable, value, path=[]):
        self.operations.append(("bind", variable, value, path))

    def add(self, graph, addnew=False):
        self.operations.append(("add" + ("new" if addnew else ""),
                                graph))

    def delete(self, graph, delex=False):
        self.operations.append(("delete" + ("existing" if delex else ""),
                                graph))

    def cut(self, variable):
        self.operations.append(("cut", variable))

    def updatelist(self, graph, subject, predicate, slice, lst):
        self.operations.append(("updatelist", subject, predicate, slice, lst, graph))


class TestStrictParser(object):
    def setUp(self):
        self.e = DummyProcessor()
        self.p = Parser(self.e, EX[''], True)

    def test_prefix_in_the_middle(self):
        with assert_raises(ParserError):
            self.p.parseString("""
            Add  { <http://example.org/a> <http://example.org/b>
                   <http://example.org/c> } .
            @prefix ex: <http://exammple.org/> .
            """)
            
    def test_prefix_sparql(self):
        with assert_raises(ParserError):
            self.p.parseString("""
            PrEfIx ex: <http://exammple.org/>
            """)

class TestParser(object):
    def setUp(self):
        self.e = DummyProcessor()
        self.p = Parser(self.e, EX[''])

    def tearDown(self):
        self.p = None
        self.e = None

    def test_prefix(self):
        self.p.parseString("@prefix foo: <http://ex.co/> .")
        eq_(("prefix", "foo", URIRef("http://ex.co/")), self.e.pop())

    def test_prefix_unicode(self):
        self.p.parseString("@prefix Iñtërnâtiônàlizætiøn: <http://ex.co/> .")
        eq_(("prefix", "Iñtërnâtiônàlizætiøn", URIRef("http://ex.co/")),
            self.e.pop())

    def test_prefix_empty(self):
        self.p.parseString("@prefix : <http://ex.co/> .")
        eq_(("prefix", "", URIRef("http://ex.co/")), self.e.pop())

    def test_prefix_sparql(self):
        self.p.parseString("PrEfIx ex: <http://ex.co/>")
        eq_(("prefix", "ex", URIRef("http://ex.co/")), self.e.pop())
        
    def test_bind(self):
        self.p.parseString("Bind ?x <http://ex.co/a> .")
        eq_(("bind", V("x"), EX.a, []), self.e.pop())

    def test_bind_relative(self):
        self.p.parseString("Bind ?x <a> .")
        eq_(("bind", V("x"), EX.a, []), self.e.pop())

    def test_bind_abbr(self):
        self.p.parseString("B ?x <http://ex.co/a> .")
        eq_(("bind", V("x"), EX.a, []), self.e.pop())

    def test_bind_path(self):
        self.p.parseString("Bind ?x <http://ex.co/a>/ex:b/^ex:c/42 .")
        eq_(("bind", V("x"), EX.a, [EX.b, InvIRI(EX.c), 42]), self.e.pop())

    def test_bind_constrained_path(self):
        self.p.parseString("Bind ?x <http://ex.co/a> /ex:b!/^ex:c[/ex:b!/^ex:c/42=0]!/42 .")
        eq_(("bind", V("x"), EX.a, [
            EX.b, UNICITY_CONSTRAINT, InvIRI(EX.c),
            PathConstraint([
                EX.b, UNICITY_CONSTRAINT,
                InvIRI(EX.c), 42
                ], Literal(0) ),
            UNICITY_CONSTRAINT, 42,
            ]),
            self.e.pop())

    def test_bind_unicode(self):
        self.p.parseString("Bind ?Iñtërnâtiônàlizætiøn <http://ex.co/a> .")
        eq_(("bind", V("Iñtërnâtiônàlizætiøn"), URIRef("http://ex.co/a"), []), self.e.pop())

    def test_cut(self):
        self.p.parseString("Cut ?x .")
        eq_(("cut", V("x")), self.e.pop())

    def test_cut_abbr(self):
        self.p.parseString("C ?x .")
        eq_(("cut", V("x")), self.e.pop())

    def test_add_empty(self):
        # NB: only in non-strict mode
        self.p.parseString("Add {}.")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eqg_(graph, [])

    def test_add_iris(self):
        self.p.parseString("Add { <http://ex.co/a> <http://ex.co/b> "
                           "<http://ex.co/c> }.")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_add_abbr(self):
        self.p.parseString("A { <http://ex.co/a> <http://ex.co/b> "
                           "<http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, EX.c) in graph, _s(graph)

    def test_add_pnames(self):
        self.p.parseString("Add { ex:a ex:b ex:cde } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, EX.cde) in graph, _s(graph)

    def test_add_Bs(self):
        self.p.parseString("Add { _:a ex:b _:cde } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (B("a"), EX.b, B("cde")) in graph, _s(graph)

    def test_add_Bs_brackets(self):
        self.p.parseString("Add { _:a ex:b [] } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        obj = graph.value(B("a"), EX.b)
        assert type(obj) is B, obj

    def test_add_variables(self):
        self.p.parseString("Add { ?a ex:b ?cde } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (V("a"), EX.b, V("cde")) in graph, _s(graph)

    def test_add_list(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b "
                           "      ( <http://ex.co/c> ex:d ) }.")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eqg_(graph, [
            (EX.a, EX.b, B("l0")),
            (B("l0"), RDF.first, EX.c),
            (B("l0"), RDF.rest, B("l1")),
            (B("l1"), RDF.first, EX.d),
            (B("l1"), RDF.rest, RDF.nil),
        ])

    def test_add_literal_integer(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b 42 } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal(42)) in graph, _s(graph)

    def test_add_literal_decimal(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b 3.14 } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("3.14", datatype=XSD.decimal)) in graph, _s(graph)

    def test_add_literal_double(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b 314e-2 } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("314e-2", datatype=XSD.double)) in graph, _s(graph)

    def test_add_literal_string(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b \"hello world\" } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("hello world")) in graph, _s(graph)

    def test_add_literal_langtag(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b \"hello world\"@en } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("hello world", "en")) in graph, _s(graph)

    def test_add_literal_datatype_iri(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b \"hello world\"^^<http://ex.co/foo> } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("hello world", datatype=EX.foo)) in graph, _s(graph)

    def test_add_literal_datatype_pname(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b \"hello world\"^^ex:foo } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("hello world", datatype=EX.foo)) in graph, _s(graph)

    def test_add_literal_unicode(self):
        self.p.parseString("Add { <http://ex.co/a> ex:b \"Iñtërnâtiônàlizætiøn☃💩\" } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eq_(len(graph), 1)
        assert (EX.a, EX.b, Literal("Iñtërnâtiônàlizætiøn☃💩")) in graph, _s(graph)

    def test_add_2triples(self):
        self.p.parseString("Add { ex:a ex:b ex:c . ex:e ex:f ex:g } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (EX.a, EX.b, EX.c),
            (EX.e, EX.f, EX.g),
        ])

    def test_add_objectlist_comma(self):
        self.p.parseString("Add { ex:a ex:b ex:c, ex:d, ex:e } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (EX.a, EX.b, EX.c),
            (EX.a, EX.b, EX.d),
            (EX.a, EX.b, EX.e),
        ])

    def test_add_objectlist_semicolon(self):
        self.p.parseString("""Add {
            ex:a
              ex:b ex:c, ex:d, ex:e ;
              ex:f ex:g ;
              ex:h ex:i, ex:j ;
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (EX.a, EX.b, EX.c),
            (EX.a, EX.b, EX.d),
            (EX.a, EX.b, EX.e),
            (EX.a, EX.f, EX.g),
            (EX.a, EX.h, EX.i),
            (EX.a, EX.h, EX.j),
        ])

    def test_add_objectlist_mixed(self):
        self.p.parseString("""Add {
            ex:a
              ex:b "txt", 10, true ;
              ex:c [], _:bn1 ;
              ex:d [
                ex:e ( ex:f _:bn1 ?v )
              ] ;
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (EX.a,    EX.b,      Literal("txt")),
            (EX.a,    EX.b,      Literal(10)),
            (EX.a,    EX.b,      Literal(True)),
            (EX.a,    EX.c,      B("n0")),
            (EX.a,    EX.c,      B("n1")),
            (EX.a,    EX.d,      B("n3")),
            (B("n3"), EX.e,      B("l1"),),
            (B("l1"), RDF.first, EX.f),
            (B("l1"), RDF.rest,  B("l2")),
            (B("l2"), RDF.first, B("n1")),
            (B("l2"), RDF.rest,  B("l3")),
            (B("l3"), RDF.first, V("v")),
            (B("l3"), RDF.rest,  RDF.nil),
        ])

    def test_add_empty_list(self):
        self.p.parseString("""Add {
            ex:a ex:b ()
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (EX.a, EX.b, RDF.nil),
        ])

    def test_add_empty_bnode(self):
        self.p.parseString("""Add {
            ex:a ex:b []
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (EX.a, EX.b, B()),
        ])

    def test_add_subject_list(self):
        self.p.parseString("""Add {
            ( ex:a ex:b ) ex:c ex:d
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (B("l1"), RDF.first, EX.a),
            (B("l1"), RDF.rest,  B("l2")),
            (B("l2"), RDF.first, EX.b),
            (B("l2"), RDF.rest,  RDF.nil),
            (B("l1"), EX.c,      EX.d),
        ])

    def test_add_subject_bnode(self):
        self.p.parseString("""Add {
            [ ex:a ex:b ] ex:c ex:d
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (B("b1"), EX.a, EX.b),
            (B("b1"), EX.c, EX.d),
        ])

    def test_add_standalone_bnode(self):
        self.p.parseString("""Add {
            [ ex:a ex:b ]
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (B("b1"), EX.a, EX.b),
        ])

    @skip("Apparently not supported by Turtle")
    def test_add_standalone_list(self):
        self.p.parseString("""Add {
            ( ex:a <http://ex.co/b> )
        } .""")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [
            (B("l1"), RDF.first, EX.a),
            (B("l1"), RDF.rest,  B("l2")),
            (B("l2"), RDF.first, EX.b),
            (B("l2"), RDF.rest,  RDF.nil),
        ])

    def test_add_keyword_a(self):
        self.p.parseString("Add { ex:a a ex:A } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "add")
        eqg_(graph, [(EX.a, RDF.type, EX.A)])

    def test_delete(self):
        self.p.parseString("Delete { <http://ex.co/a> <http://ex.co/b> "
                           "         <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "delete")
        eq_(len(graph), 1)
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_delete_abbr(self):
        self.p.parseString("D { <http://ex.co/a> <http://ex.co/b> "
                           "    <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "delete")
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    # assuming that parsing the 'Delete' graph is the same as
    # parsing the 'Add' the graph, we do not duplicate all the tests ;
    # idem for AddNew and DeleteExisting below.

    def test_addnew(self):
        self.p.parseString("AddNew { <http://ex.co/a> <http://ex.co/b> "
                           "         <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "addnew")
        eq_(len(graph), 1)
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_addnew_abbr(self):
        self.p.parseString("AN { <http://ex.co/a> <http://ex.co/b> "
                           "    <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "addnew")
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_deleteexisting(self):
        self.p.parseString("DeleteExisting { <http://ex.co/a> <http://ex.co/b> "
                           "         <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "deleteexisting")
        eq_(len(graph), 1)
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_deleteexisting_abbr(self):
        self.p.parseString("DE { <http://ex.co/a> <http://ex.co/b> "
                           "    <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_(cmd, "deleteexisting")
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_updatelist_point(self):
        self.p.parseString("UpdateList ?x ex:p 3 ( <http://ex.co/a> ex:b \"foo\" 42 ) .")
        got = self.e.pop() ; graph = got[-1]
        eq_(len(got), 6)
        eq_(("updatelist", V("x"), EX.p, Slice(3, 4)), got[:4])
        eq_([ EX.a, EX.b, Literal("foo"), Literal(42) ],
            list(Collection(graph, got[-2])))

    def test_updatelist_abbr(self):
        self.p.parseString("UL ?x ex:p 3 ( <http://ex.co/a> ex:b \"foo\" 42 ) .")
        got = self.e.pop() ; graph = got[-1]
        eq_(len(got), 6)
        eq_(("updatelist", V("x"), EX.p, Slice(3, 4)), got[:4])
        eq_([ EX.a, EX.b, Literal("foo"), Literal(42) ],
            list(Collection(graph, got[-2])))

    def test_updatelist_til_the_end(self):
        self.p.parseString("UpdateList ?x ex:p 3.. ( <http://ex.co/a> ex:b \"foo\" 42 ) .")
        got = self.e.pop() ; graph = got[-1]
        eq_(len(got), 6)
        eq_(("updatelist", V("x"), EX.p, Slice(3, None)), got[:4])
        eq_([ EX.a, EX.b, Literal("foo"), Literal(42) ],
            list(Collection(graph, got[-2])))

    def test_updatelist_slice(self):
        self.p.parseString("UpdateList ?x ex:p 3..7 ( <http://ex.co/a> ex:b \"foo\" 42 ) .")
        got = self.e.pop() ; graph = got[-1]
        eq_(len(got), 6)
        eq_(("updatelist", V("x"), EX.p, Slice(3, 7)), got[:4])
        eq_([ EX.a, EX.b, Literal("foo"), Literal(42) ],
            list(Collection(graph, got[-2])))

    def test_updatelist_at_the_end(self):
        self.p.parseString("UpdateList ?x ex:p .. ( <http://ex.co/a> ex:b \"foo\" 42 ) .")
        got = self.e.pop() ; graph = got[-1]
        eq_(len(got), 6)
        eq_(("updatelist", V("x"), EX.p, Slice(None, None)), got[:4])
        eq_([ EX.a, EX.b, Literal("foo"), Literal(42) ],
            list(Collection(graph, got[-2])))

    def test_updatelist_empty(self):
        self.p.parseString("UpdateList ?x ex:p 3 () .")
        got = self.e.pop() ; graph = got[-1]
        eq_(len(got), 6)
        eq_(("updatelist", V("x"), EX.p, Slice(3, 4)), got[:4])
        eq_([], list(Collection(graph, got[-2])))

    def test_add_multiline(self):
        self.p.parseString("Add {\n"
                           "  <http://ex.co/a>\n"
                           "    <http://ex.co/b>\n"
                           "      <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_comment(self):
        self.p.parseString("# hello world\n")
        self.e.is_empty()

    def test_comment_in_the_middle(self):
        self.p.parseString("Add {\n"
                           "  <http://ex.co/a>\n"
                           "  # hello world\n"
                           "    <http://ex.co/b>\n"
                           "      <http://ex.co/c> } .")
        cmd, graph = self.e.pop()
        eq_("add", cmd)
        eqg_(graph, [(EX.a, EX.b, EX.c)])

    def test_add_clears_graph(self):
        self.p.parseString("""
            Add { ex:a ex:b ex:c }.
            Add { ex:d ex:e ex:f }.
        """)
        # check that the second graph is not poluted by the first one
        _, graph = self.e.pop()
        eqg_(graph, [(EX.d, EX.e, EX.f)])

    def test_del_clears_graph(self):
        self.p.parseString("""
            Delete { ex:a ex:b ex:c }.
            Add { ex:d ex:e ex:f }.
        """)
        # check that the second graph is not poluted by the first one
        _, graph = self.e.pop()
        eqg_(graph, [(EX.d, EX.e, EX.f)])

    def test_updatelist_clears_graph(self):
        self.p.parseString("""
            UpdateList ex:a ex:b 1..2 ( ex:a ex:b ex:c ).
            Add { ex:d ex:e ex:f }.
        """)
        # check that the second graph is not poluted by the first one
        _, graph = self.e.pop()
        eqg_(graph, [(EX.d, EX.e, EX.f)])

