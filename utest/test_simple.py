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
from __future__ import unicode_literals

from nose.tools import assert_raises, assert_list_equal, eq_
from rdflib import BNode, Literal, Namespace, URIRef, Variable as V, XSD

from ldpatch.engine import InvIRI, PathConstraint, Slice, UNICITY_CONSTRAINT
from ldpatch.simple import Parser

EX = Namespace("http://ex.co/")


class DummyEngine(object):
    def __init__(self):
        self.operations = []

    def pop(self):
        return self.operations.pop()

    def expand_pname(self, prefix, suffix=""):
        return URIRef(EX[suffix])

    def prefix(self, prefix, iri):
        self.operations.append(("prefix", prefix, iri))

    def bind(self, variable, path):
        self.operations.append(("bind", variable, path))

    def add(self, subject, predicate, object):
        self.operations.append(("add", subject, predicate, object))

    def delete(self, subject, predicate, object):
        self.operations.append(("delete", subject, predicate, object))

    def replace(self, subject, predicate, slice, lst):
        self.operations.append(("replace", subject, predicate, slice, lst))



class TestSimpleParser(object):
    def setUp(self):
        self.e = DummyEngine()
        self.p = Parser(self.e)

    def tearDown(self):
        self.p = None
        self.e = None

    def test_prefix(self):
        self.p.parseString("Prefix foo: <http://ex.co/>")
        eq_(("prefix", "foo", URIRef("http://ex.co/")), self.e.pop())

    def test_prefix_unicode(self):
        self.p.parseString("Prefix Iñtërnâtiônàlizætiøn: <http://ex.co/>")
        eq_(("prefix", "Iñtërnâtiônàlizætiøn", URIRef("http://ex.co/")),
            self.e.pop())

    def test_prefix_empty(self):
        self.p.parseString("Prefix : <http://ex.co/>")
        eq_(("prefix", "", URIRef("http://ex.co/")), self.e.pop())

    def test_bind(self):
        self.p.parseString("Bind ?x <http://ex.co/a>")
        eq_(("bind", V("x"), [EX.a]), self.e.pop())

    def test_bind_path(self):
        self.p.parseString("Bind ?x <http://ex.co/a>/ex:b/-ex:c/42")
        eq_(("bind", V("x"), [EX.a, EX.b, InvIRI(EX.c), 42]), self.e.pop())

    def test_bind_constrained_path(self):
        self.p.parseString("Bind ?x <http://ex.co/a>/ex:b!/-ex:c[ex:b!/-ex:c/42=0]!/42")
        eq_(("bind", V("x"), [EX.a, EX.b, UNICITY_CONSTRAINT, InvIRI(EX.c),
                              PathConstraint([EX.b, UNICITY_CONSTRAINT,
                                              InvIRI(EX.c), 42
                                             ], Literal(0)
                              ),
                              UNICITY_CONSTRAINT, 42,
                              ]),
            self.e.pop())

    def test_bind_unicode(self):
        self.p.parseString("Bind ?Iñtërnâtiônàlizætiøn <http://ex.co/a>")
        eq_(("bind", V("Iñtërnâtiônàlizætiøn"), [URIRef("http://ex.co/a")]), self.e.pop())

    def test_add_iris(self):
        self.p.parseString("Add <http://ex.co/a> <http://ex.co/b> "
                           "<http://ex.co/c>")
        eq_(("add", EX.a, EX.b, EX.c), self.e.pop())

    def test_add_pnames(self):
        self.p.parseString("Add ex:a ex:b ex:cde")
        eq_(("add", EX.a, EX.b, EX.cde), self.e.pop())

    def test_add_bnodes(self):
        self.p.parseString("Add _:a ex:b _:cde")
        eq_(("add", BNode("a"), EX.b, BNode("cde")), self.e.pop())

    def test_add_variables(self):
        self.p.parseString("Add ?a ex:b ?cde")
        eq_(("add", V("a"), EX.b, V("cde")), self.e.pop())

    def test_add_list(self):
        self.p.parseString("Add <http://ex.co/a> ex:b ( <http://ex.co/c> ex:d )")
        eq_(("add", EX.a, EX.b, [EX.c, EX.d]), self.e.pop())

    def test_add_literal_integer(self):
        self.p.parseString("Add <http://ex.co/a> ex:b 42")
        eq_(("add", EX.a, EX.b, Literal(42)), self.e.pop())

    def test_add_literal_decimal(self):
        self.p.parseString("Add <http://ex.co/a> ex:b 3.14")
        eq_(("add", EX.a, EX.b, Literal("3.14", datatype=XSD.decimal)),
            self.e.pop())

    def test_add_literal_double(self):
        self.p.parseString("Add <http://ex.co/a> ex:b 314e-2")
        eq_(("add", EX.a, EX.b, Literal("314e-2", datatype=XSD.double)),
            self.e.pop())

    def test_add_literal_integer(self):
        self.p.parseString("Add <http://ex.co/a> ex:b 42")
        eq_(("add", EX.a, EX.b, Literal(42)), self.e.pop())

    def test_add_literal_string(self):
        self.p.parseString("Add <http://ex.co/a> ex:b \"hello world\"")
        eq_(("add", EX.a, EX.b, Literal("hello world")), self.e.pop())

    def test_add_literal_langtag(self):
        self.p.parseString("Add <http://ex.co/a> ex:b \"hello world\"@en")
        eq_(("add", EX.a, EX.b, Literal("hello world", "en")), self.e.pop())

    def test_add_literal_datatype_iri(self):
        self.p.parseString("Add <http://ex.co/a> ex:b \"hello world\"^^<http://ex.co/foo>")
        eq_(("add", EX.a, EX.b, Literal("hello world", datatype=EX.foo)),
            self.e.pop())

    def test_add_literal_datatype_pname(self):
        self.p.parseString("Add <http://ex.co/a> ex:b \"hello world\"^^ex:foo")
        eq_(("add", EX.a, EX.b, Literal("hello world", datatype=EX.foo)),
            self.e.pop())

    def test_add_literal_unicode(self):
        self.p.parseString("Add <http://ex.co/a> ex:b \"Iñtërnâtiônàlizætiøn☃💩\"")
        eq_(("add", EX.a, EX.b, Literal("Iñtërnâtiônàlizætiøn☃💩")),
            self.e.pop())

    def test_delete_iris(self):
        self.p.parseString("Delete <http://ex.co/a> <http://ex.co/b> "
                           "<http://ex.co/c>")
        eq_(("delete", EX.a, EX.b, EX.c), self.e.pop())

    def test_delete_pnames(self):
        self.p.parseString("Delete ex:a ex:b ex:cde")
        eq_(("delete", EX.a, EX.b, EX.cde), self.e.pop())

    def test_delete_bnodes(self):
        self.p.parseString("Delete _:a ex:b _:cde")
        eq_(("delete", BNode("a"), EX.b, BNode("cde")), self.e.pop())

    def test_delete_variables(self):
        self.p.parseString("Delete ?a ex:b ?cde")
        eq_(("delete", V("a"), EX.b, V("cde")), self.e.pop())

    def test_delete_literal_integer(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b 42")
        eq_(("delete", EX.a, EX.b, Literal(42)), self.e.pop())

    def test_delete_literal_decimal(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b 3.14")
        eq_(("delete", EX.a, EX.b, Literal("3.14", datatype=XSD.decimal)),
            self.e.pop())

    def test_delete_literal_double(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b 314e-2")
        eq_(("delete", EX.a, EX.b, Literal("314e-2", datatype=XSD.double)),
            self.e.pop())

    def test_delete_literal_integer(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b 42")
        eq_(("delete", EX.a, EX.b, Literal(42)), self.e.pop())

    def test_delete_literal_string(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b \"hello world\"")
        eq_(("delete", EX.a, EX.b, Literal("hello world")), self.e.pop())

    def test_delete_literal_langtag(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b \"hello world\"@en")
        eq_(("delete", EX.a, EX.b, Literal("hello world", "en")), self.e.pop())

    def test_delete_literal_datatype_iri(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b \"hello world\"^^<http://ex.co/foo>")
        eq_(("delete", EX.a, EX.b, Literal("hello world", datatype=EX.foo)),
            self.e.pop())

    def test_delete_literal_datatype_pname(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b \"hello world\"^^ex:foo")
        eq_(("delete", EX.a, EX.b, Literal("hello world", datatype=EX.foo)),
            self.e.pop())

    def test_delete_literal_unicode(self):
        self.p.parseString("Delete <http://ex.co/a> ex:b \"Iñtërnâtiônàlizætiøn☃💩\"")
        eq_(("delete", EX.a, EX.b, Literal("Iñtërnâtiônàlizætiøn☃💩")),
            self.e.pop())

    def test_replace_point(self):
        self.p.parseString("Replace ?x ex:p 3 ( <http://ex.co/a> ex:b \"foo\" 42 )")
        eq_(("replace", V("x"), EX.p, Slice(3),
             [ EX.a, EX.b, Literal("foo"), Literal(42) ]),
            self.e.pop())

    def test_replace_til_the_end(self):
        self.p.parseString("Replace ?x ex:p 3> ( <http://ex.co/a> ex:b \"foo\" 42 )")
        eq_(("replace", V("x"), EX.p, Slice(3, '>'),
             [ EX.a, EX.b, Literal("foo"), Literal(42) ]),
            self.e.pop())

    def test_replace_slice(self):
        self.p.parseString("Replace ?x ex:p 3>7 ( <http://ex.co/a> ex:b \"foo\" 42 )")
        eq_(("replace", V("x"), EX.p, Slice(3, '>', 7),
             [ EX.a, EX.b, Literal("foo"), Literal(42) ]),
            self.e.pop())

    def test_replace_at_the_end(self):
        self.p.parseString("Replace ?x ex:p > ( <http://ex.co/a> ex:b \"foo\" 42 )")
        eq_(("replace", V("x"), EX.p, Slice(None, '>'),
             [ EX.a, EX.b, Literal("foo"), Literal(42) ]),
            self.e.pop())

    def test_replace_empty(self):
        self.p.parseString("Replace ?x ex:p 3 ()")
        eq_(("replace", V("x"), EX.p, Slice(3), []),
            self.e.pop())
