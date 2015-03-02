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

import sys
from os.path import dirname
sys.path.append(dirname(dirname(__file__)))

from nose.tools import assert_raises, assert_set_equal, eq_
from rdflib import BNode as B, Graph, Literal, Namespace, Variable as V
from rdflib.compare import isomorphic
from rdflib.collection import Collection
from unittest import skip

from ldpatch.processor import *

INITIAL = """
@prefix v: <http://example.org/vocab#> .
@prefix f: <http://xmlns.com/foaf/0.1/> .

<http://champin.net/#pa>
    f:name "Pierre-Antoine Champin" ;
    v:prefLang ( "fr" "en" "tlh" ) ;
    f:knows
        [
            f:name "Alexandre Bertails" ;
            f:holdsAccount [
                f:accountName "bertails" ;
                f:accountServiceHomepage <http://twitter.com/>
            ];
            v:prefLang ( "en" "fr" ) ;
        ],
        [
            f:name "Andrei Sambra" ;
            f:holdsAccount [
                f:accountName "therealdeiu" ;
                f:accountServiceHomepage <http://twitter.com/>
            ];
        ];
.

_:ucbl
    f:name "Université Claude Bernard Lyon 1" ;
    f:member <http://champin.net/#pa>, _:am .

_:am f:name "Alain Mille" .
"""

VOCAB = Namespace("http://example.org/vocab#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
PA = IRI("http://champin.net/#pa")

def G(data):
    g = Graph()
    if type(data) is list:
        g_add = g.add
        for i in data: g_add(i)
    else:
        g.parse(data=data, format="turtle")
    return g

V = Variable

class TestPatchProcessor(object):
    def setUp(self):
        self.g = G(INITIAL)
        self.e = PatchProcessor(self.g,
                             {"foaf": IRI(FOAF), "vocab": IRI(VOCAB)})
        self.my_friends = { t[2] for t in self.g.triples((PA, FOAF.knows, None)) }
        self.ucbl = self.g.value(None, FOAF.member, PA)

    def tearDown(self):
        self.e = None
        self.g = None

    # intermediate method

    def _my_updatelist(self, subj, pred, slice, items):
        """
        I expose a simpler interface than PatchProcessor.updatelist
        """
        graph_lst = Graph()
        if len(items) == 0:
            lst = RDF.nil
        else:
            lst = BNode()
            Collection(graph_lst, lst, items)
            assert len(graph_lst) == 2*len(items), graph_lst.serialize(format="n3")
        return self.e.updatelist(graph_lst, subj, pred, slice, lst)

    # testing utility methods

    def test_getnode_variable_unbound(self):
        with assert_raises(UnboundVariableError):
            self.e.get_node(V("foo"))

    def test_getnode_variable(self):
        self.e = PatchProcessor(self.g, init_vars={V("x"): PA})
        eq_(PA, self.e.get_node(V("x")))

    def test_getnode_bnode_same_twice(self):
        bnid = BNode()
        created = self.e.get_node(bnid)
        assert bnid is not created
        assert created is self.e.get_node(bnid)

    def test_getnode_bnode_different(self):
        created1 = self.e.get_node(BNode())
        created2 = self.e.get_node(BNode())
        assert created1 != created2

    def test_getnode_iri(self):
        eq_(PA, self.e.get_node(PA))

    def test_getnode_iri_absent(self):
        eq_(VOCAB.foo, self.e.get_node(VOCAB.foo))

    def test_getnode_literal(self):
        txt = Literal("Pierre-Antoine Champin")
        eq_(txt, self.e.get_node(txt))

    def test_getnode_literal_absent(self):
        txt = Literal("this text is not in the data")
        eq_(txt, self.e.get_node(txt))


    def test_dopathstep_iri_one_start(self):
        assert_set_equal(self.my_friends,
                         self.e.do_path_step({PA}, FOAF.knows))

    def test_dopathstep_iri_several_starts(self):
        assert_set_equal({Literal("Alexandre Bertails"), Literal("Andrei Sambra")},
                         self.e.do_path_step(self.my_friends, FOAF.name))

    def test_dopathstep_iri_partial_match(self):
        eq_(1, len(self.e.do_path_step(self.my_friends, VOCAB.prefLang)))

    def test_dopathstep_inv_one_start(self):
        assert_set_equal({self.ucbl},
                          self.e.do_path_step({PA}, InvIRI(FOAF.member)))

    def test_dopathstep_inv_several_starts(self):
        assert_set_equal({PA},
                         self.e.do_path_step(self.my_friends, InvIRI(FOAF.knows)))

    def test_dopathstep_inv_partial_match(self):
        assert_set_equal({self.ucbl},
                         self.e.do_path_step(self.my_friends | {PA}, InvIRI(FOAF.member)))

    def test_dopathstep_int_one_start(self):
        self.preflang = self.g.value(PA, VOCAB.prefLang)
        assert_set_equal({Literal("en")},
                          self.e.do_path_step({self.preflang}, 1))

    def test_dopathstep_int_multiple_start(self):
        starts = { trpl[2] for trpl in self.g.triples((None, VOCAB.prefLang, None)) }
        assert_set_equal({Literal("en"), Literal("fr")},
                          self.e.do_path_step(starts, 1))

    def test_dopathstep_int_partial_match(self):
        starts = { trpl[2] for trpl in self.g.triples((None, VOCAB.prefLang, None)) }
        assert_set_equal({Literal("tlh")},
                          self.e.do_path_step(starts, 2))

    def test_dopathstep_unique_one_start(self):
        assert_set_equal({PA}, self.e.do_path_step({PA}, UNICITY_CONSTRAINT))

    def test_dopathstep_unique_multiple_start(self):
        with assert_raises(NoUniqueMatchError):
            self.e.do_path_step(self.my_friends, UNICITY_CONSTRAINT)

    def test_dopathstep_unique_zero_start(self):
        with assert_raises(NoUniqueMatchError):
            self.e.do_path_step({}, UNICITY_CONSTRAINT)

    def test_pathconstraint_simple(self):
        constraint = PathConstraint([FOAF.holdsAccount])
        for i in self.my_friends:
            assert self.e.test_path_constraint(i, constraint)
        assert not self.e.test_path_constraint(PA, constraint)

    def test_pathconstraint_value(self):
        constraint = PathConstraint([FOAF.name], Literal("Pierre-Antoine Champin"))
        for i in self.my_friends:
            assert not self.e.test_path_constraint(i, constraint)
        assert self.e.test_path_constraint(PA, constraint)

    def test_pathconstraint_unicity(self):
        constraint = PathConstraint([FOAF.knows, UNICITY_CONSTRAINT])
        for i in self.my_friends:
            assert not self.e.test_path_constraint(i, constraint)
        assert not self.e.test_path_constraint(PA, constraint)


    # testing the ldpatch commands

    def test_prefix_once(self):
        self.e.prefix("foo", IRI(FOAF))
        eq_(FOAF.Person, self.e.expand_pname("foo", "Person"))

    def test_prefix_twice(self):
        self.e.prefix("foo", IRI(FOAF))
        self.e.prefix("foo", IRI(VOCAB))
        eq_(VOCAB.Person, self.e.expand_pname("foo", "Person"))

    def test_bind_once(self):
        self.e.bind(V("foo"), VOCAB.foo, [])
        eq_(VOCAB.foo, self.e.get_node(V("foo")))

    def test_bind_twice(self):
        self.e.bind(V("foo"), VOCAB.foo, [])
        self.e.bind(V("foo"), VOCAB.bar, [])
        eq_(VOCAB.bar, self.e.get_node(V("foo")))

    def test_bind_too_few(self):
        with assert_raises(NoUniqueMatchError):
            self.e.bind(V("foo"), PA, [VOCAB.notUsed])

    def test_bind_too_many(self):
        with assert_raises(NoUniqueMatchError):
            self.e.bind(V("foo"), PA, [FOAF.knows])

    def test_bind_from_variable(self):
        self.e.bind(V("ucbl"), PA, [InvIRI(FOAF.member) ])
        self.e.bind(V("pa"), V("ucbl"), [
            FOAF.member,
            PathConstraint([FOAF.name], Literal("Pierre-Antoine Champin")),
        ])
        eq_(PA, self.e.get_node(V("pa")))

    def test_add_simple(self):
        self.e.add(G([(PA, RDF.type, FOAF.Person)]))
        exp = G(INITIAL + """<http://champin.net/#pa> a f:Person .""")
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_complex(self):
        g2add = G([(PA, VOCAB.favNumbers, B("l1"))])
        Collection(g2add, B("l1"), [ Literal(i) for i in (42, 7, 2, 10) ])
        self.e.add(g2add)
        exp = G(INITIAL + """<http://champin.net/#pa> v:favNumbers (42 7 2 10) .""")
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_variable_subject(self):
        self.e.bind(V("s"), PA, [InvIRI(FOAF.member)])
        self.e.add(G([
            (V("s"), FOAF.homepage, IRI("http://www.univ-lyon1.fr/")),
        ]))
        exp = G(INITIAL + """_:ucbl f:homepage <http://www.univ-lyon1.fr/>.""")
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_variable_object(self):
        self.e.bind(V("o"), PA, [InvIRI(FOAF.member)])
        self.e.add(G([(PA, VOCAB.memberOf, V("o")),]))
        exp = G(INITIAL + """<http://champin.net/#pa> v:memberOf _:ucbl.""")
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_one_variable_multiple_times(self):
        self.e.bind(V("x"), PA, [InvIRI(FOAF.member)])
        self.e.add(G([
            (V("x"), FOAF.homepage, IRI("http://www.univ-lyon1.fr/")),
            (PA    , FOAF.knows,    IRI("http://doe.org/#john")),
            (IRI("http://doe.org/#john"), VOCAB.memberOf, V("x")),
        ]))
        exp = G(INITIAL + """
            _:ucbl f:homepage <http://www.univ-lyon1.fr/> .
            <http://champin.net/#pa> f:knows <http://doe.org/#john> .
            <http://doe.org/#john> v:memberOf _:ucbl .
        """)
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_two_variables_multiple_times(self):
        self.e.bind(V("x"), PA, [InvIRI(FOAF.member)])
        self.e.bind(V("y"), Literal("Alain Mille"), [InvIRI(FOAF.name)])
        self.e.add(G([
            (V("x"), FOAF.homepage, IRI("http://www.univ-lyon1.fr/")),
            (PA    , FOAF.knows,    V("y")),
            (V("y"), VOCAB.memberOf, V("x")),
        ]))
        exp = G(INITIAL + """
            _:ucbl f:homepage <http://www.univ-lyon1.fr/> .
            <http://champin.net/#pa> f:knows _:am .
            _:am v:memberOf _:ucbl .
        """)
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_bnode(self):
        # deliberately reusing a BNode label from the original graph ('ucbl'),
        # to check that a fresh bnode is nonetheless created
        mytwitter = BNode("ucbl")
        self.e.add(G([
            (PA, FOAF.holdsAccount, mytwitter),
            (mytwitter, FOAF.accountName, Literal("pchampin")),
        ]))
        exp = G(INITIAL + """<http://champin.net/#pa> f:holdsAccount [ """
                          """    f:accountName "pchampin"\n].""")
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_add_two_bnodes(self):
        # check that distinct bnodes in the source graph
        # generate distinct fresh bnodes in the target graph ;
        # as above, try to mess with existing bnode labels to check robustness
        jdoe = BNode("ucbl")
        jdup = BNode("am")
        self.e.add(G([
            (PA, FOAF.knows, jdoe),
            (jdoe, FOAF.givenName, Literal("John")),
            (jdoe, FOAF.familyName, Literal("Doe")),
            (PA, FOAF.knows, jdup),
            (jdup, FOAF.givenName, Literal("Jeanne")),
            (jdup, FOAF.familyName, Literal("Dupont")),
        ]))
        exp = G(INITIAL + """
            <http://champin.net/#pa> f:knows
                [
                    f:givenName "John" ;
                    f:familyName "Doe" ;
                ],
                [
                    f:givenName "Jeanne" ;
                    f:familyName "Dupont" ;
                ];
            .
        """)
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_delete_simple(self):
        self.e.delete(G([
            (PA, FOAF.name, Literal("Pierre-Antoine Champin")),
        ]))
        exp = G(INITIAL.replace("""f:name "Pierre-Antoine Champin" ;""", ""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_delete_variable_subject(self):
        self.e.bind(V("s"), PA, [InvIRI(FOAF.member)])
        self.e.delete(G([
            (V("s"), FOAF.name, Literal("Université Claude Bernard Lyon 1")),
        ]))
        exp = G(INITIAL.replace("""f:name "Université Claude Bernard Lyon 1" ;""", ""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_delete_variable_object(self):
        # no easy way to test it in the current graph,
        # so we add an arc and remove it again...
        self.g.add((PA, VOCAB.memberOf, self.ucbl))
        self.e.bind(V("o"), PA, [InvIRI(FOAF.member)])
        self.e.delete(G([
            (PA, VOCAB.memberOf, V("o")),
        ]))
        exp = G(INITIAL)
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_cut_simple(self):
        x = B("x")
        y = B("y")
        z = B("z")
        self.g.add((PA, VOCAB.test, x))
        self.g.add((x, VOCAB.foo, Literal("foo")))
        self.g.add((x, VOCAB.bar, y))
        self.g.add((y, VOCAB.foo, z))
        self.g.add((y, VOCAB.bar, Literal("bar")))
        self.g.add((z, VOCAB.foo, x))
        self.g.add((z, VOCAB.bar, PA))
        self.g.add((z, VOCAB.baz, z))

        self.e.bind(V("x"), Literal("foo"), [InvIRI(VOCAB.foo),])
        self.e.cut(V("x"))
        exp = G(INITIAL)
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_cut_wrong_node(self):
        with assert_raises(CutExpectsBnodeError):
            self.e.cut(PA)

    def test_cut_fails(self):
        with assert_raises(CurRemovedNothing):
            self.e.cut(B())
        

    def test_updatelist_item(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, 2), [ Literal("en-US") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""", """( "fr" "en-US" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_first_item(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 1), [ Literal("fr-FR") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""", """( "fr-FR" "en" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_last_item(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(2, 3), [ Literal("TLH") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""", """( "fr" "en" "TLH" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_item_with_several(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, 2), [ Literal("en-US"), Literal("en-GB") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "en-US" "en-GB" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_first_item_with_several(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 1), [ Literal("fr-FR"), Literal("fr-BE") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr-FR" "fr-BE" "en" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_last_item_with_several(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(2, 3), [ Literal("tlh-k1"), Literal("tlh-k2") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "en" "tlh-k1" "tlh-k2" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_item_with_none(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, 2), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_first_item_with_none(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 1), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "en" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_last_item_with_none(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(2, 3), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "en" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_insert_begin(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 0), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "a" "b" "fr" "en" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_insert_middle(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, 1), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "a" "b" "en" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_append(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(None, None), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "en" "tlh" "a" "b")"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_cut_begin(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 2), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_cut_middle(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, 2), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_cut_end(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, None), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_cut_all(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, None), [])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """()"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_change_begin(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 2), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "a" "b" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_change_middle(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, 2), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "a" "b" "tlh" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_change_end(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(1, None), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "fr" "a" "b" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_change_all(self):
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, None), [ Literal("a"), Literal("b") ])
        exp = G(INITIAL.replace("""( "fr" "en" "tlh" )""",
                                """( "a" "b" )"""))
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_cut_bnodes(self):
        bn = B()
        self.g.set((self.g.value(PA, VOCAB.prefLang), RDF.first, bn))
        self.g.set((bn, VOCAB.foo, Literal("foo")))
        if not isomorphic(self.g, G(INITIAL.replace('''( "fr" "en" "tlh" )''', '''( [v:foo "foo"] "en" "tlh" )'''))):
            raise ValueError("Error while setting up test...")
        
        self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 1), [])
        exp = G(INITIAL.replace('''( "fr" "en" "tlh" )''', '''( "en" "tlh" )'''))
        # NB: no trace for the arc  ''' _:nb v:foo "foo" ''' in the graph
        got = self.g
        assert isomorphic(got, exp), got.serialize(format="turtle")

    def test_updatelist_outofbound_imin(self):
        with assert_raises(OutOfBoundUpdateListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(4, None), [ Literal("a"), Literal("b") ])

    def test_updatelist_outofbound_imax(self):
        with assert_raises(OutOfBoundUpdateListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(0, 4), [ Literal("a"), Literal("b") ])

    def test_updatelist_too_many_matches(self):
        self.g.add((PA, VOCAB.prefLang, RDF.nil))
        with assert_raises(NoUniqueMatchError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(1, None), [])

    def test_updatelist_too_few_matches(self):
        self.g.remove((PA, VOCAB.prefLang, None))
        with assert_raises(NoUniqueMatchError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(1, None), [])

    def test_updatelist_malformed_rest_toomany_before(self):
        self.g.add((self.g.value(PA, VOCAB.prefLang), RDF.rest, B()))
        with assert_raises(MalformedListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(1, None), [])

    def test_updatelist_malformed_rest_toofew_before(self):
        self.g.remove((self.g.value(PA, VOCAB.prefLang), RDF.rest, None))
        with assert_raises(MalformedListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(1, None), [])

    def test_updatelist_malformed_rest_toomany(self):
        self.g.add((self.g.value(PA, VOCAB.prefLang), RDF.rest, B()))
        with assert_raises(MalformedListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(0, None), [])

    def test_updatelist_malformed_rest_toofew(self):
        self.g.remove((self.g.value(PA, VOCAB.prefLang), RDF.rest, None))
        with assert_raises(MalformedListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(0, None), [])

    def test_updatelist_malformed_first_toomany(self):
        self.g.add((self.g.value(PA, VOCAB.prefLang), RDF.first, B()))
        with assert_raises(MalformedListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(0, None), [])

    def test_updatelist_malformed_first_toofew(self):
        self.g.remove((self.g.value(PA, VOCAB.prefLang), RDF.first, None))
        with assert_raises(MalformedListError):
            self._my_updatelist(PA, VOCAB.prefLang, Slice(0, None), [])

    def test_updatelist_malformed_udl_1(self):
        with assert_raises(ValueError):
            graph_lst = Graph()
            head = B("head")
            graph_lst.add((B("head"), RDF.first, Literal("a")));
            graph_lst.add((B("head"), RDF.rest, B("n1")));
            graph_lst.add((B("n1"), RDF.first, Literal("b")));
            graph_lst.add((B("n1"), RDF.rest, B("n2")));
            graph_lst.add((B("n2"), RDF.first, Literal("c")));
            self.e.updatelist(graph_lst, PA, VOCAB.prefLang, Slice(1,None), B("head"))

    def test_updatelist_malformed_udl_2(self):
        with assert_raises(ValueError):
            graph_lst = Graph()
            head = B("head")
            graph_lst.add((B("head"), RDF.first, Literal("a")));
            graph_lst.add((B("head"), RDF.rest, B("n1")));
            graph_lst.add((B("n1"), RDF.first, Literal("b")));
            graph_lst.add((B("n1"), RDF.rest, B("n2")));
            graph_lst.add((B("n2"), RDF.first, Literal("c")));
            graph_lst.add((B("n2"), RDF.rest, RDF.nil));
            graph_lst.add((B("n2"), RDF.rest, B("n3")));
            self.e.updatelist(graph_lst, PA, VOCAB.prefLang, Slice(1,None), B("head"))

        


    # the following tests demonstrate how
    # complex identification schemes for bnodes are supported by ldpatch
    #

    def test_identify_ucbl_1(self):
        # the only organization of which PA is a member
        self.e.bind(Variable("ucbl"), PA,
                    [ InvIRI(FOAF.member), UNICITY_CONSTRAINT ])
        exp = self.g.value(None, FOAF.name,
                           Literal("Université Claude Bernard Lyon 1"))
        eq_(exp, self.e.get_node(Variable("ucbl")))

    def test_identify_ucbl_2(self):
        # the organization of which PA is a member, which is named UCBL
        self.e.bind(Variable("ucbl"), PA, [
            InvIRI(FOAF.member),
            PathConstraint(
                [FOAF.name],
                Literal("Université Claude Bernard Lyon 1")
            )
        ])
        eq_(self.ucbl, self.e.get_node(Variable("ucbl")))

    def test_identify_alexandre(self):
        # the person that PA knows and whose twitter name is bertails
        self.e.bind(Variable("ab"), PA, [
            FOAF.knows,
            PathConstraint([
                FOAF.holdsAccount,
                PathConstraint(
                    [FOAF.accountServiceHomepage],
                    IRI("http://twitter.com/")
                ),
                FOAF.accountName,
            ], Literal("bertails"))
        ])
        exp = self.g.value(None, FOAF.name, Literal("Alexandre Bertails"))
        eq_(exp, self.e.get_node(Variable("ab")))

    def test_identify_alexandre_twitter_account(self):
        # the twitter account of the person that PA knows whose name is AB
        self.e.bind(Variable("ab"), PA, [
            FOAF.knows,
            PathConstraint(
                [FOAF.name],
                Literal("Alexandre Bertails")
            ),
            UNICITY_CONSTRAINT,
            FOAF.holdsAccount,
            PathConstraint(
                [FOAF.accountServiceHomepage],
                IRI("http://twitter.com/")
            )
        ])
        exp = self.g.value(None, FOAF.accountName, Literal("bertails"))
        eq_(exp, self.e.get_node(Variable("ab")))

