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
Generate unit-tests from the LD-Patch test suite.

The test suite can be downloaded from
<https://github.com/pchampin/ld-patch-testsuite>
.
"""
from os.path import dirname, exists, join
from unittest import skip, TestCase
from urllib import pathname2url, urlopen

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.collection import Collection
from rdflib.compare import isomorphic

from ldpatch.processor import PatchProcessor, PatchEvalError
from ldpatch.syntax import Parser, ParserError

TESTSUITE_PATH = join(dirname(dirname(__file__)), "ld-patch-testsuite")
MF = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#")
RDFT = Namespace("http://www.w3.org/ns/rdftest#")

BLACKLIST = {
    # not working because the Turtle parser in RDFlib does not fully support
    # unicodeEscapes in localNames:
    "localName_with_assigned_nfc_PN_CHARS_BASE_character_boundaries",
}

class LdPatchTestSuite(TestCase):

    def test_suite_present(self):
        assert exists(TESTSUITE_PATH)
        # the TestCase must contain at least one test,
        # or the fact that it is skipped (if TESTSUITE_PATH does not exist)
        # will *not* appear in any report


if exists(TESTSUITE_PATH):

    class DummyProcessor(object):
        def __init__(self):
            self.prefices = {}
        def expand_pname(self, prefix, suffix=""):
            ns = self.prefices.get(prefix)
            if ns is None:
                raise ParserError("Undeclared prefix")
            return URIRef("{}{}".format(ns, suffix))
        def prefix(self, prefix, iri):
            self.prefices[prefix] = iri
        def bind(self, variable, value, path=[]):
            pass
        def add(self, graph, addnew=False):
            pass
        def delete(self, graph, delex=False):
            pass
        def cut(self, var):
            pass
        def updatelist(self, graph, subject, predicate, slice, lst):
            pass


    MANIFEST_PATH = join(TESTSUITE_PATH, "manifest.ttl")
    MANIFEST_IRI = URIRef("file://{}".format(pathname2url(MANIFEST_PATH)))
    NS = Namespace(MANIFEST_IRI + "#")

    def populate_testsuite(manifest_iri):

        manifest = Graph(); manifest.load(manifest_iri, format="turtle")
        get_value = manifest.value

        includes = Collection(manifest, get_value(manifest_iri, MF.include))
        for include in includes:
            populate_testsuite(include)

        entries = Collection(manifest, get_value(manifest_iri, MF.entries))
        for entry in entries:
            etype = get_value(entry, RDF.type)
            approval = get_value(entry, RDFT.approval, default=RDFT.Approved)
            name = unicode(get_value(entry, MF.name))
            # /!\ variables assigned in the loop can not be safely used
            # inside the function (as they will all inherit the *last*
            # value of those variables, so 'entry' is passed as a default
            # parameter, and all useful values derived from 'entry' must be
            # computed *inside* the functions)

            if name in BLACKLIST:
                @skip("Blacklisted entry {}".format(entry))
                def test_X(self):
                    pass
            elif approval == NS.Skipped:
                #### do not pollute the test output with skipped tests
                #@skip("Unapproved entry {}".format(entry))
                #def test_X(self):
                #    pass
                #### instead:
                continue
            elif etype == NS.PositiveSyntaxTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, MF.action)
                    patch = urlopen(action).read()
                    parser = Parser(DummyProcessor(), action, True)
                    try:
                        parser.parseString(patch)
                    except ParserError, ex:
                        assert False, "{} in <{}>".format(ex, action)
            elif etype == NS.NegativeSyntaxTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, MF.action)
                    patch = urlopen(action).read()
                    parser = Parser(DummyProcessor(), action, True)
                    try:
                        parser.parseString(patch)
                        assert False,\
                                "expected ParserError in <{}>".format(action)
                    except ParserError:
                        pass
            elif etype == NS.PositiveEvaluationTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, MF.action)
                    data_iri = get_value(action, NS.data)
                    patch_iri = get_value(action, NS.patch)
                    base_iri = get_value(action, NS.base) or data_iri
                    result_iri = get_value(entry, MF.result)
                    data = Graph(); data.load(data_iri, publicID=base_iri, format="turtle")
                    patch = urlopen(patch_iri).read()
                    result = Graph(); result.load(result_iri, publicID=base_iri, format="turtle")
                    processor = PatchProcessor(data)
                    parser = Parser(processor, base_iri, True)
                    try:
                        parser.parseString(patch)
                    except ParserError, ex:
                        raise Exception("ParseError: {}\n  in <{}>".format(
                            ex.message,
                            patch_iri
                        ))
                    assert isomorphic(data, result), (
                        "\n  patch: <{}>\n  result: {}\n".format(
                            patch_iri,
                            data.serialize(format="turtle"),
                        )
                    )
            elif etype == NS.NegativeEvaluationTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, MF.action)
                    data_iri = get_value(action, NS.data)
                    patch_iri = get_value(action, NS.patch)
                    base_iri = get_value(action, NS.base) or data_iri
                    data = Graph(); data.load(data_iri, publicID=base_iri, format="turtle")
                    patch = urlopen(patch_iri).read()
                    processor = PatchProcessor(data)
                    parser = Parser(processor, base_iri, True)
                    try:
                        parser.parseString(patch)
                        assert False, 'expected PatchEvalError in <{}>'.format(
                            patch_iri
                        )
                    except PatchEvalError:
                        pass
            else:
                @skip("Unknown test type {}".format(etype))
                def test_X(self):
                    pass

            name = "test_{}".format(name)
            if hasattr(LdPatchTestSuite, name):
                i = 2
                while hasattr(LdPatchTestSuite, "{}_{}".format(name, i)):
                    i += 1
                name = "{}_{}".format(name, i)

            test_X.__name__ = name
            setattr(LdPatchTestSuite, name, test_X)
            del test_X # prevents node from running it as a test
        
    populate_testsuite(MANIFEST_IRI)
    del populate_testsuite # prevents nose from running it as a test

else:
    msg = "ld-patch-testuite could not be found at {}".format(TESTSUITE_PATH)
    LdPatchTestSuite = skip(msg)(LdPatchTestSuite)
