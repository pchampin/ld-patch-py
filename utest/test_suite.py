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

from ldpatch.engine import PatchEngine, PatchEvalError
from ldpatch.simple import Parser, ParserError

TESTSUITE_PATH = join(dirname(dirname(__file__)), "ld-patch-testsuite")

class LdPatchTestSuite(TestCase):

    def test_suite(self):
        assert exists(TESTSUITE_PATH)
        # the TestCase must contain at least one test,
        # or the fact that it is skipped (if TESTSUITE_PATH does not exist)
        # will *not* appear in any report


if exists(TESTSUITE_PATH):

    class DummyEngine(object):
        def expand_pname(self, prefix, suffix=""):
            return URIRef("http://example.org/{}".format(suffix))
        def prefix(self, prefix, iri):
            pass
        def bind(self, variable, value, path):
            pass
        def add(self, subject, predicate, object):
            pass
        def delete(self, subject, predicate, object):
            pass
        def updatelist(self, subject, predicate, slice, lst):
            pass

    def populate_testsuite():
        manifest_path = join(TESTSUITE_PATH, "manifest.ttl")
        manifest_iri = URIRef("file://{}".format(pathname2url(manifest_path)))
        mf = Namespace(
            "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#")
        ns = Namespace(manifest_iri + "#")

        manifest = Graph(); manifest.load(manifest_iri, format="turtle")
        get_value = manifest.value

        entries = Collection(manifest, get_value(manifest_iri, mf.entries))
        for entry in entries:
            etype = get_value(entry, RDF.type)
            # /!\ variables assigned in the loop can not be safely used
            # inside the function (as they will all inherit the *last*
            # value of those variables, so 'entry' is passed as a default
            # parameter, and all useful values derived from 'entry' must be
            # computed *inside* the functions)

            if etype == ns.PositiveSyntaxTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, mf.action)
                    patch = urlopen(action).read()
                    parser = Parser(DummyEngine(), action, True)
                    try:
                        parser.parseString(patch)
                    except ParserError, ex:
                        assert False, ex
            elif etype == ns.NegativeSyntaxTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, mf.action)
                    patch = urlopen(action).read()
                    parser = Parser(DummyEngine(), action, True)
                    try:
                        parser.parseString(patch)
                        assert False, "expected ParserError"
                    except ParserError:
                        pass
            elif etype == ns.PositiveEvaluationTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, mf.action)
                    data_iri = get_value(action, ns.data)
                    patch_iri = get_value(action, ns.patch)
                    base_iri = get_value(action, ns.base) or data_iri
                    result_iri = get_value(entry, mf.result)
                    data = Graph(); data.load(data_iri, format="turtle")
                    patch = urlopen(patch_iri).read()
                    result = Graph(); result.load(result_iri, format="turtle")
                    engine = PatchEngine(data)
                    parser = Parser(engine, base_iri, True)
                    parser.parseString(patch)
                    assert isomorphic(data, result), \
                        got.serialize(format="turtle")
            elif etype == ns.NegativeEvaluationTest:
                def test_X(self, entry=entry):
                    action = get_value(entry, mf.action)
                    data_iri = get_value(action, ns.data)
                    patch_iri = get_value(action, ns.patch)
                    base_iri = get_value(action, ns.base) or data_iri
                    data = Graph(); data.load(data_iri, format="turtle")
                    patch = urlopen(patch_iri).read()
                    engine = PatchEngine(data)
                    parser = Parser(engine, base_iri, True)
                    try:
                        parser.parseString(patch)
                        assert False, "expected PatchEvalError"
                    except PatchEvalError:
                        pass
            else:
                @skip("Unknown test type {}".format(etype))
                def test_X(self):
                    pass

            name = "test_{}".format(get_value(entry, mf.name))
            test_X.__name__ = name
            setattr(LdPatchTestSuite, name, test_X)
            del test_X # prevents node from running it as a test
        
    populate_testsuite()
    del populate_testsuite # prevents nose from running it as a test

else:
    msg = "ld-patch-testuite could not be found at {}".format(TESTSUITE_PATH)
    LdPatchTestSuite = skip(msg)(LdPatchTestSuite)
