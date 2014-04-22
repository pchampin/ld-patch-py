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
import sys
from os.path import dirname
sys.path.append(dirname(dirname(__file__)))

from cStringIO import StringIO
from pyparsing import ParseException
from rdflib import Graph
from rdflib.compare import isomorphic
from unittest import skip

from patch import ROW, Patch


INITIAL = """
@prefix v: <http://example.org/vocab#> .
@prefix f: <http://xmlns.com/foaf/0.1/> .

<http://champin.net/#pa>
    f:name "Pierre-Antoine Champin" ;
    v:prefLang ( "fr" "en" ) ;
    f:knows
        [
            f:name "Andy Seaborne" ;
            v:memberOf [
                f:name "Epimorphic Ltd" ;
            ];
        ],
        [
            f:name "Sandro Hawke" ;
            v:memberOf [
                f:name "World Wide Web Consortium" ;
            ];
        ];
.

_:ucbl
    f:name "Université Claude Bernard Lyon 1" ;
    f:member <http://champin.net/#pa> .
"""

def G(data):
    g = Graph()
    g.parse(data=data, format="turtle")
    return g

def P(data):
    return Patch(StringIO(data))


def test_parse_line():
    for line, exp in {
            'Add <tag:s> <tag:p> <tag:o> .':
                ['Add', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'Add <tag:s> <tag:p> "foo" .':
                ['Add', '<tag:s>', ['<tag:p>'], ['"foo"', None, None], None],
            'Add <tag:s> <tag:p> "foo"@en .':
                ['Add', '<tag:s>', ['<tag:p>'], ['"foo"', "en", None], None],
            'Add <tag:s> <tag:p> "foo"^^<tag:t> .':
                ['Add', '<tag:s>', ['<tag:p>'], ['"foo"', None, "<tag:t>"],
                 None],
            'Add R <tag:p> <tag:o> .':
                ['Add', 'R', ['<tag:p>'], '<tag:o>', None],
            'Add R R <tag:o> .':
                ['Add', 'R', 'R', '<tag:o>', None],
            'Add <tag:s> <tag:p> <tag:o> <tag:g>.':
                ['Add', '<tag:s>', ['<tag:p>'], '<tag:o>', '<tag:g>'],
            'Add <tag:s> <tag:p> <tag:o> R.':
                ['Add', '<tag:s>', ['<tag:p>'], '<tag:o>', 'R'],
            'Add R <tag:p> <tag:o> R.':
                ['Add', 'R', ['<tag:p>'], '<tag:o>', 'R'],
            'Add R R <tag:o> R.':
                ['Add', 'R', 'R', '<tag:o>', 'R'],
            'Add <tag:s> -<tag:p> <tag:o> .':
                ['Add', '<tag:s>', [['-', '<tag:p>']], '<tag:o>', None],
            'Add <tag:s> <tag:p>/<tag:q> <tag:o> .':
                ['Add', '<tag:s>', ['<tag:p>', '<tag:q>'], '<tag:o>', None],
            'Add <tag:s> <tag:p>/-<tag:q> <tag:o> .':
                ['Add', '<tag:s>', ['<tag:p>', ['-', '<tag:q>']], '<tag:o>',
                 None],
            'Ad <tag:s> <tag:p> <tag:o> .':
                ['Ad', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'A <tag:s> <tag:p> <tag:o> .':
                ['A', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'Delete <tag:s> <tag:p> <tag:o>.':
                ['Delete', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'Delete <tag:s> <tag:p> <tag:o> <tag:g>.':
                ['Delete', '<tag:s>', ['<tag:p>'], '<tag:o>', '<tag:g>'],
            'Del <tag:s> <tag:p> <tag:o>.':
                ['Del', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'D <tag:s> <tag:p> <tag:o>.':
                ['D', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'Replace <tag:s> <tag:p> <tag:o>.':
                ['Replace', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'Replace <tag:s> <tag:p> <tag:o> <tag:g>.':
                ['Replace', '<tag:s>', ['<tag:p>'], '<tag:o>', '<tag:g>'],
            'Replace <tag:s> <tag:p>[1] <tag:o>.':
                ['Replace', '<tag:s>', ['<tag:p>', ['[', '1']], '<tag:o>', None],
            'Replace <tag:s> <tag:p>[0:] ( <tag:o> "foo" _:bar ).':
                ['Replace', '<tag:s>', ['<tag:p>', ['[', '0', ':']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'Replace <tag:s> <tag:p>[0:2] ( <tag:o> "foo" _:bar ).':
                ['Replace', '<tag:s>', ['<tag:p>', ['[', '0', ':', '2']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'Replace <tag:s> <tag:p>[:2] ( <tag:o> "foo" _:bar ).':
                ['Replace', '<tag:s>', ['<tag:p>', ['[', ':', '2']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'Replace <tag:s> <tag:p>[:] ( <tag:o> "foo" _:bar ).':
                ['Replace', '<tag:s>', ['<tag:p>', ['[', ':']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'Replace <tag:s> <tag:p>[] ( <tag:o> "foo" _:bar ).':
                ['Replace', '<tag:s>', ['<tag:p>', ['[']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'Repl <tag:s> <tag:p> <tag:o>.':
                ['Repl', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'R <tag:s> <tag:p> <tag:o>.':
                ['R', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'Clear <tag:s> <tag:p>.':
                ['Clear', '<tag:s>', ['<tag:p>'], None],
            'Clear <tag:s> <tag:p> <tag:g>.':
                ['Clear', '<tag:s>', ['<tag:p>'], '<tag:g>', None],
            'Cl <tag:s> <tag:p>.':
                ['Cl', '<tag:s>', ['<tag:p>'], None],
            'C <tag:s> <tag:p>.':
                ['C', '<tag:s>', ['<tag:p>'], None],
        }.iteritems():
        try:
            got = ROW.parseString(line, True).asList()
            assert got == exp, "%s\n -> %r" % (line, got)
        except ParseException, ex:
            assert False, "%s\n -> %s" % (line, ex)

def test_add_simple():
    p = P("""Add <http://champin.net/#pa>"""
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .""")
    exp = G(INITIAL + """<http://champin.net/#pa> a f:Person .""")

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_simple_among_others():
    p = P("""Add <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/knows>"""
          """ <http://danbri.org/foaf.rdf#danbri> .""")
    exp = G(INITIAL + """<http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/knows>"""
          """ <http://danbri.org/foaf.rdf#danbri> .""")

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_simple_existing():
    p = P("""Add <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "Pierre-Antoine Champin" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_add_inverse():
    p = P("""Add <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/knows>"""
          """ <http://danbri.org/foaf.rdf#danbri> .""")
    exp = G(INITIAL + """
        <http://danbri.org/foaf.rdf#danbri>
            <http://xmlns.com/foaf/0.1/knows>
                <http://champin.net/#pa> .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_path():
    p = P("""Add <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member>"""
          """ /<http://example.org/vocab#famousMember>"""
          """ <http://johndoe.org/#me> .""")
    exp = G(INITIAL + """
        _:ucbl v:famousMember <http://johndoe.org/#me> .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

    p = P("""Add <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member>"""
          """ /<http://example.org/vocab#famousMember>"""
          """ /<http://xmlns.com/foaf/0.1/name>"""
          """ "John Doe" .""")
    exp = G(INITIAL + """
        _:ucbl v:famousMember <http://johndoe.org/#me> .
        <http://johndoe.org/#me> f:name "John Doe" .
    """)

    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_path_existing():
    p = P("""Add <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member>"""
          """ /<http://xmlns.com/foaf/0.1/name>"""
          """ "Université Claude Bernard Lyon 1" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_literal_as_subject():
    p = P("""Add "Andy Seaborne" """
          """ -<http://xmlns.com/foaf/0.1/name>"""
          """ /<http://xmlns.com/foaf/0.1/nick>"""
          """ "AndyS" .""")
    exp = G(INITIAL.replace('"Andy Seaborne"',
                            '"Andy Seaborne"; f:nick "AndyS"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_path_with_index():
    p = P("""Add <http://champin.net/#pa> """
          """ <http://example.org/vocab#prefLang>[1]"""
          """ /-<http://example.org/vocab#speaksFluently>"""
          """ <http://champin.net/#pa> .""")
    exp = G(INITIAL + """
        <http://champin.net/#pa> v:speaksFluently "en" .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_del_simple():
    p = P("""Delete <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "Pierre-Antoine Champin" .""")
    exp = G(INITIAL.replace("""f:name "Pierre-Antoine Champin" ;""", ""))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_del_simple_inexisting():
    p = P("""Delete <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "PAC" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_del_path():
    p = P("""Delete <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "Université Claude Bernard Lyon 1" .""")
    exp = G(INITIAL.replace("""f:name "Université Claude Bernard Lyon 1" ;""",
                            ""))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_del_path_inexisting():
    p = P("""Delete <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "UCBL" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_clear_simple():
    p = P("""Clear <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/knows> .""")
    exp = G("""
        @prefix v: <http://example.org/vocab#> .
        @prefix f: <http://xmlns.com/foaf/0.1/> .

        <http://champin.net/#pa>
            f:name "Pierre-Antoine Champin" ;
            v:prefLang ( "fr" "en" ) ;
        .

        _:ucbl
            f:name "Université Claude Bernard Lyon 1" ;
            f:member <http://champin.net/#pa> .
        
        [] v:memberOf [ f:name "World Wide Web Consortium" ] ;
           f:name "Sandro Hawke" .

        [] v:memberOf [ f:name "Epimorphic Ltd" ] ;
           f:name "Andy Seaborne" .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_clear_simple_inexisting():
    p = P("""Clear <http://champin.net/#pa> """
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_clear_path():
    p = P("""Clear <http://champin.net/#pa> """
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ .""")
    exp = G(INITIAL.replace("""f:name "Université Claude Bernard Lyon 1" ;""",
                            ""))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_simple():
    p = P("""Replace <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "PAC" .""")
    exp = G(INITIAL.replace('"Pierre-Antoine Champin"', '"PAC"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_simple_existing():
    p = P("""Replace <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "Pierre-Antoine Champin" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_simple_inexisting():
    p = P("""Replace <http://champin.net/#pa> """
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .""")
    exp = G(INITIAL + """<http://champin.net/#pa> a f:Person .""")

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_repl_path():
    p = P("""Replace <http://champin.net/#pa> """
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "UCBL" .""")
    exp = G(INITIAL.replace('"Université Claude Bernard Lyon 1"', '"UCBL"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_path_existing():
    p = P("""Replace <http://champin.net/#pa> """
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "Université Claude Bernard Lyon 1" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_path_inexisting():
    p = P("""Replace <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member>"""
          """ /<http://example.org/vocab#famousMember>"""
          """ <http://johndoe.org/#me> .""")
    exp = G(INITIAL + """
        _:ucbl v:famousMember <http://johndoe.org/#me> .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_index():
    p = P("""Replace <http://champin.net/#pa>"""
          """ <http://example.org/vocab#prefLang>[1]"""
          """ "en-UK" .""")
    exp = G(INITIAL.replace('"en"', '"en-UK"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_slice():
    p = P("""Replace <http://champin.net/#pa>"""
          """ <http://example.org/vocab#prefLang>[1:]"""
          """ ("en-UK" "en-US" "en") .""")
    exp = G(INITIAL.replace('"en"', '"en-UK" "en-US" "en"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_whole_slice():
    p = P("""Replace <http://champin.net/#pa>"""
          """ <http://example.org/vocab#prefLang>[:]"""
          """ () .""")
    exp = G(INITIAL.replace(
            '( "fr" "en" )',
            "<http://www.w3.org/1999/02/22-rdf-syntax-ns#nil>"))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repeat_subject():
    p = P("""Add <http://champin.net/#pa>"""
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .\n"""
          """Add R <http://xmlns.com/foaf/0.1/nick> "pchampin" .""")
    exp = G(INITIAL + """
        <http://champin.net/#pa> a f:Person; f:nick "pchampin" .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repeat_predicate():
    p = P("""Add <http://champin.net/#pa>"""
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .\n"""
          """Add <http://champin.net/#pa> R"""
          """ <http://xmlns.com/foaf/0.1/Agent> .""")
    exp = G(INITIAL + """
        <http://champin.net/#pa> a f:Person, f:Agent .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repeat_object():
    p = P("""Add <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/nick> "pchampin" .\n"""
          """Add <http://champin.net/#pa>"""
          """ <http://example.org/vocab#login> R .""")
    exp = G(INITIAL + """
        <http://champin.net/#pa> f:nick "pchampin" ; v:login "pchampin" .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

@skip("write this test")
def test_bnode_creation():
    pass

# TODO test all error conditions as well
# TODO test with named graph as well
# TODO test in unsafe mode
