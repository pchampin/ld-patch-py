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
            'A <tag:s> <tag:p> <tag:o> .':
                ['A', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'A <tag:s> <tag:p> "foo" .':
                ['A', '<tag:s>', ['<tag:p>'], ['"foo"', None, None], None],
            'A <tag:s> <tag:p> "foo"@en .':
                ['A', '<tag:s>', ['<tag:p>'], ['"foo"', "en", None], None],
            'A <tag:s> <tag:p> "foo"^^<tag:t> .':
                ['A', '<tag:s>', ['<tag:p>'], ['"foo"', None, "<tag:t>"],
                 None],
            'A R <tag:p> <tag:o> .':
                ['A', 'R', ['<tag:p>'], '<tag:o>', None],
            'A R R <tag:o> .':
                ['A', 'R', 'R', '<tag:o>', None],
            'A <tag:s> <tag:p> <tag:o> <tag:g>.':
                ['A', '<tag:s>', ['<tag:p>'], '<tag:o>', '<tag:g>'],
            'A <tag:s> <tag:p> <tag:o> R.':
                ['A', '<tag:s>', ['<tag:p>'], '<tag:o>', 'R'],
            'A R <tag:p> <tag:o> R.':
                ['A', 'R', ['<tag:p>'], '<tag:o>', 'R'],
            'A R R <tag:o> R.':
                ['A', 'R', 'R', '<tag:o>', 'R'],
            'A <tag:s> -<tag:p> <tag:o> .':
                ['A', '<tag:s>', [['-', '<tag:p>']], '<tag:o>', None],
            'A <tag:s> <tag:p>/<tag:q> <tag:o> .':
                ['A', '<tag:s>', ['<tag:p>', '<tag:q>'], '<tag:o>', None],
            'A <tag:s> <tag:p>/-<tag:q> <tag:o> .':
                ['A', '<tag:s>', ['<tag:p>', ['-', '<tag:q>']], '<tag:o>',
                 None],
            'D <tag:s> <tag:p> <tag:o>.':
                ['D', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'D <tag:s> <tag:p> <tag:o> <tag:g>.':
                ['D', '<tag:s>', ['<tag:p>'], '<tag:o>', '<tag:g>'],
            'R <tag:s> <tag:p> <tag:o>.':
                ['R', '<tag:s>', ['<tag:p>'], '<tag:o>', None],
            'R <tag:s> <tag:p> <tag:o> <tag:g>.':
                ['R', '<tag:s>', ['<tag:p>'], '<tag:o>', '<tag:g>'],
            'R <tag:s> <tag:p>[1] <tag:o>.':
                ['R', '<tag:s>', ['<tag:p>', ['[', '1']], '<tag:o>', None],
            'R <tag:s> <tag:p>[0:] ( <tag:o> "foo" _:bar ).':
                ['R', '<tag:s>', ['<tag:p>', ['[', '0', ':']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'R <tag:s> <tag:p>[0:2] ( <tag:o> "foo" _:bar ).':
                ['R', '<tag:s>', ['<tag:p>', ['[', '0', ':', '2']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'R <tag:s> <tag:p>[:2] ( <tag:o> "foo" _:bar ).':
                ['R', '<tag:s>', ['<tag:p>', ['[', ':', '2']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'R <tag:s> <tag:p>[:] ( <tag:o> "foo" _:bar ).':
                ['R', '<tag:s>', ['<tag:p>', ['[', ':']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'R <tag:s> <tag:p>[] ( <tag:o> "foo" _:bar ).':
                ['R', '<tag:s>', ['<tag:p>', ['[']],
                 ['(', '<tag:o>', ['"foo"', None, None], "_:bar"], None],
            'C <tag:s> <tag:p>.':
                ['C', '<tag:s>', ['<tag:p>'], None],
            'C <tag:s> <tag:p> <tag:g>.':
                ['C', '<tag:s>', ['<tag:p>'], '<tag:g>', None],
        }.iteritems():
        try:
            got = ROW.parseString(line, True).asList()
            assert got == exp, "%s\n -> %r" % (line, got)
        except ParseException, ex:
            assert False, "%s\n -> %s" % (line, ex)

def test_add_simple():
    p = P("""A <http://champin.net/#pa>"""
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .""")
    exp = G(INITIAL + """<http://champin.net/#pa> a f:Person .""")

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_simple_among_others():
    p = P("""A <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/knows>"""
          """ <http://danbri.org/foaf.rdf#danbri> .""")
    exp = G(INITIAL + """<http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/knows>"""
          """ <http://danbri.org/foaf.rdf#danbri> .""")

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_simple_existing():
    p = P("""A <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "Pierre-Antoine Champin" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_add_inverse():
    p = P("""A <http://champin.net/#pa>"""
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
    p = P("""A <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member>"""
          """ /<http://example.org/vocab#famousMember>"""
          """ <http://johndoe.org/#me> .""")
    exp = G(INITIAL + """
        _:ucbl v:famousMember <http://johndoe.org/#me> .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

    p = P("""A <http://champin.net/#pa>"""
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
    p = P("""A <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member>"""
          """ /<http://xmlns.com/foaf/0.1/name>"""
          """ "Université Claude Bernard Lyon 1" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_literal_as_subject():
    p = P("""A "Andy Seaborne" """
          """ -<http://xmlns.com/foaf/0.1/name>"""
          """ /<http://xmlns.com/foaf/0.1/nick>"""
          """ "AndyS" .""")
    exp = G(INITIAL.replace('"Andy Seaborne"',
                            '"Andy Seaborne"; f:nick "AndyS"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_add_path_with_index():
    p = P("""A <http://champin.net/#pa> """
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
    p = P("""D <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "Pierre-Antoine Champin" .""")
    exp = G(INITIAL.replace("""f:name "Pierre-Antoine Champin" ;""", ""))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_del_simple_inexisting():
    p = P("""D <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "PAC" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_del_path():
    p = P("""D <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "Université Claude Bernard Lyon 1" .""")
    exp = G(INITIAL.replace("""f:name "Université Claude Bernard Lyon 1" ;""",
                            ""))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_del_path_inexisting():
    p = P("""D <http://champin.net/#pa>"""
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "UCBL" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_clear_simple():
    p = P("""C <http://champin.net/#pa> """
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
    p = P("""C <http://champin.net/#pa> """
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_clear_path():
    p = P("""C <http://champin.net/#pa> """
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ .""")
    exp = G(INITIAL.replace("""f:name "Université Claude Bernard Lyon 1" ;""",
                            ""))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_simple():
    p = P("""R <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "PAC" .""")
    exp = G(INITIAL.replace('"Pierre-Antoine Champin"', '"PAC"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_simple_existing():
    p = P("""R <http://champin.net/#pa> """
          """ <http://xmlns.com/foaf/0.1/name> """
          """ "Pierre-Antoine Champin" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_simple_inexisting():
    p = P("""R <http://champin.net/#pa> """
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .""")
    exp = G(INITIAL + """<http://champin.net/#pa> a f:Person .""")

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")
    
def test_repl_path():
    p = P("""R <http://champin.net/#pa> """
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "UCBL" .""")
    exp = G(INITIAL.replace('"Université Claude Bernard Lyon 1"', '"UCBL"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_path_existing():
    p = P("""R <http://champin.net/#pa> """
          """ -<http://xmlns.com/foaf/0.1/member> """
          """ /<http://xmlns.com/foaf/0.1/name> """
          """ "Université Claude Bernard Lyon 1" .""")
    exp = G(INITIAL)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_path_inexisting():
    p = P("""R <http://champin.net/#pa>"""
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
    p = P("""R <http://champin.net/#pa>"""
          """ <http://example.org/vocab#prefLang>[1]"""
          """ "en-UK" .""")
    exp = G(INITIAL.replace('"en"', '"en-UK"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_slice():
    p = P("""R <http://champin.net/#pa>"""
          """ <http://example.org/vocab#prefLang>[1:]"""
          """ ("en-UK" "en-US" "en") .""")
    exp = G(INITIAL.replace('"en"', '"en-UK" "en-US" "en"'))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repl_whole_slice():
    p = P("""R <http://champin.net/#pa>"""
          """ <http://example.org/vocab#prefLang>[:]"""
          """ () .""")
    exp = G(INITIAL.replace(
            '( "fr" "en" )',
            "<http://www.w3.org/1999/02/22-rdf-syntax-ns#nil>"))

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repeat_subject():
    p = P("""A <http://champin.net/#pa>"""
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .\n"""
          """A R <http://xmlns.com/foaf/0.1/nick> "pchampin" .""")
    exp = G(INITIAL + """
        <http://champin.net/#pa> a f:Person; f:nick "pchampin" .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repeat_predicate():
    p = P("""A <http://champin.net/#pa>"""
          """ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"""
          """ <http://xmlns.com/foaf/0.1/Person> .\n"""
          """A <http://champin.net/#pa> R"""
          """ <http://xmlns.com/foaf/0.1/Agent> .""")
    exp = G(INITIAL + """
        <http://champin.net/#pa> a f:Person, f:Agent .
    """)

    got = G(INITIAL)
    p.apply_to(got)
    assert isomorphic(got, exp), got.serialize(format="turtle")

def test_repeat_object():
    p = P("""A <http://champin.net/#pa>"""
          """ <http://xmlns.com/foaf/0.1/nick> "pchampin" .\n"""
          """A <http://champin.net/#pa>"""
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
