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
I implement a parser for a simple LD-Patch syntax.

Design note
-----------

The grammar is split in two parts:
* the static part, defined at the module level,
  contains all rules that do not depend on namespace declarations,
  so their parse-actions are context-free;

* the contextual part, defined for each instance of Parser,
  contains all rules that are depending on namespace declarations,
  so their parse-actions are bound to instance methods,
  as they depend on the state of the parser at a given time.

To prevent re-generating the grammar for each new ldpatch,
Parser has a ``reset`` method that allows to restart it afresh.

"""
from pyparsing import Combine, Forward, Group, Keyword, Literal, OneOrMore, Optional, ParseException, Regex, restOfLine, Suppress, ZeroOrMore
from re import compile as regex, VERBOSE

import rdflib
from rdflib.collection import Collection as RdfCollection

import engine

RDF_NIL = rdflib.RDF.nil

# the following rules are from the SPARQL syntax
# http://www.w3.org/TR/2013/REC-sparql11-query-20130321/

PLX = Regex(r"%[0-9a-fA-F]{2}|\\[_~.\-!$&\'()*+,;=/?#@%]")
PN_CHARS_BASE= Regex(ur'[A-Z]|[a-z]|[\u00C0-\u00D6]|[\u00D8-\u00F6]|[\u00F8-\u02FF]|[\u0370-\u037D]|[\u037F-\u1FFF]|[\u200C-\u200D]|[\u2070-\u218F]|[\u2C00-\u2FEF]|[\u3001-\uD7FF]|[\uF900-\uFDCF]|[\uFDF0-\uFFFD]|[\U00010000-\U000EFFFF]')
PN_CHARS_U = PN_CHARS_BASE | '_'
PN_CHARS = PN_CHARS_U | '-' | Regex(ur'[0-9]|\u00B7|[\u0300-\u036F]|[\u203F-\u2040]')

# NB: PN_PREFIX, PN_LOCAL and BLANK_NODE_LABEL are defined
# in a slightly different way than in the SPARQL grammar,
# to accomodate for the greedy parsing of pyparsing;
# it should nonetheless be equivalent
#    A ( (B|'.')* B )?

PN_PREFIX = Combine(
    PN_CHARS_BASE
    + ZeroOrMore(PN_CHARS)
    + ZeroOrMore(OneOrMore('.') + OneOrMore(PN_CHARS))
)("prefix")
PN_LOCAL = Combine(
    (PN_CHARS_U | ':' | Regex('[0-9]') | PLX)
    + ZeroOrMore(PN_CHARS | ':' | PLX)
    + ZeroOrMore(OneOrMore('.') + OneOrMore(PN_CHARS | ':' | PLX))
)("suffix")
BLANK_NODE_LABEL = Combine(
    '_:'
    + ( PN_CHARS_U | Regex('[0-9]') )
    + ZeroOrMore(PN_CHARS)
    + ZeroOrMore(OneOrMore('.') + OneOrMore(PN_CHARS))
)

PNAME_NS = Combine(Optional(PN_PREFIX, "") + Suppress(':'))
PNAME_LN = Combine(PNAME_NS + PN_LOCAL)
IRIREF = Regex(r'<([^\x00-\x20<>"{}|^`\\]|\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8})*>')
ECHAR =  Regex(r'''\\[tbnrf"'\\]''')
UCHAR = Regex(r'\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}')
STRING_LITERAL_QUOTE = Combine(Suppress('"') + ZeroOrMore(Regex(r'[^\x22\x5C\x0A\x0D]') | ECHAR | UCHAR) + Suppress('"'))
STRING_LITERAL_SINGLE_QUOTE = Combine(Suppress("'") + ZeroOrMore(Regex(r'[^\x27\x5C\x0A\x0D]') | ECHAR | UCHAR) + Suppress("'"))
STRING_LITERAL_LONG_SINGLE_QUOTE = Combine(Suppress("'''") + ZeroOrMore(Regex(r"'{0,2}") + (Regex(r"[^'\\]") | ECHAR | UCHAR)) + Suppress("'''"))
STRING_LITERAL_LONG_QUOTE = Combine(Suppress('"""') + ZeroOrMore(Regex(r'"{0,2}') + (Regex(r'[^"\\]') | ECHAR | UCHAR)) + Suppress('"""'))
STRING = STRING_LITERAL_LONG_SINGLE_QUOTE | STRING_LITERAL_LONG_QUOTE | STRING_LITERAL_QUOTE | STRING_LITERAL_SINGLE_QUOTE
LANGTAG = Suppress('@') + Regex(r'[a-zA-Z]+(-[a-zA-Z0-9]+)*')
INTEGER = Regex(r'[+-]?[0-9]+')
DECIMAL = Regex(r'[+-]?[0-9]*\.[0-9]+')
EXPONENT = Regex(r'[eE][+-]?[0-9]+')
DOUBLE = Combine(Regex(r'[+-]?[0-9]+\.[0-9]*|[+-]?\.?[0-9]+|[+-]?\.?[0-9]+') + EXPONENT)
NUMERIC_LITERAL = DOUBLE | DECIMAL | INTEGER
BOOLEAN_LITERAL = Regex(r'true|false')
ANON = Literal("[") + Literal("]")

# other context-independant rules
VARIABLE = Combine(
    Regex(r'[?$]') + ( PN_CHARS_U | Regex(r'[0-9]') )
    +  ZeroOrMore(PN_CHARS_U | Regex(u'[0-9]|\u00B7|[\u0300-\u036F]|[\u203F-\u2040]'))
)
INDEX = Regex(r'[0-9]+')
UNICITY_CONSTRAINT = Literal('!')
SLICE = INDEX + Optional('..' + Optional(INDEX) ) | '..'
COMMA = Suppress(",")
SEMICOLON = Suppress(";")
PERIOD = Suppress(".")
BIND_CMD = Suppress(Literal("Bind") | Literal("B"))
ADD_CMD = Suppress(Literal("Add") | Literal("A"))
DELETE_CMD = Suppress(Literal("Delete") | Literal("D"))
UPDATELIST_CMD = Suppress(Literal("UpdateList") | Literal("UL"))


@BLANK_NODE_LABEL.setParseAction
def parse_bnode(s, loc, toks):
    return rdflib.BNode(toks[0][2:])

@ANON.setParseAction
def parse_bnode(s, loc, toks):
    return rdflib.BNode()

@INTEGER.setParseAction
def parse_integer(s, loc, toks):
    return rdflib.Literal(toks[0], datatype=rdflib.XSD.integer)

@DECIMAL.setParseAction
def parse_decimal(s, loc, toks):
    return rdflib.Literal(toks[0], datatype=rdflib.XSD.decimal)

@DOUBLE.setParseAction
def parse_double(s, loc, toks):
    return rdflib.Literal(u"".join(toks), datatype=rdflib.XSD.double)

@BOOLEAN_LITERAL.setParseAction
def parse_decimal(s, loc, toks):
    return rdflib.Literal(toks[0], datatype=rdflib.XSD.boolean)

@VARIABLE.setParseAction
def parse_variable(s, loc, toks):
    return engine.Variable(toks[0][1:])

@INDEX.setParseAction
def parse_index(s, loc, toks):
    return int(toks[0])

@UNICITY_CONSTRAINT.setParseAction
def parse_unicityconstraint(s, loc, toks):
    return engine.UNICITY_CONSTRAINT

@SLICE.setParseAction
def parse_slice(s, loc, toks):
    if toks[0] == '..':   # ".."
        return engine.Slice(None, None)
    elif len(toks) == 1:  # <index>
        return engine.Slice(toks[0], toks[0]+1)
    elif len(toks) == 2:  # <index> ".."
        return engine.Slice(toks[0], None)
    else:                 # <index> ".." <index>
        return engine.Slice(toks[0], toks[2])


# unescaping
IRI_ESCAPE_SEQ = regex(ur"\\u([0-9A-Fa-f]{4}) | \\U([0-9A-Fa-f]{8})", VERBOSE)
LOCAL_ESCAPE_SEQ = regex(ur"\\([_~.\-!$&'()*+,;=/?#@%])", VERBOSE)
STRING_ESCAPE_SEQ = regex(ur"\\u([0-9A-Fa-f]{4}) | \\U([0-9A-Fa-f]{8}) "
                          ur" | \\([tbnrf\\\"'])", VERBOSE)
STRING_UNESCAPE_MAP = { "t": "\t", "b": "\b", "n": "\n", "r": "\r", "f": "\f",
                        "\\": "\\", '"': '"', "'": "'" }

def unescape_iri(iri):
    def repl(match):
        groups = match.groups()
        return unichr(int(groups[0] or groups[1], 16))
    return IRI_ESCAPE_SEQ.sub(repl, iri)

def unescape_local_name(local):
    return LOCAL_ESCAPE_SEQ.sub(r"\1", local)

def unescape_string(string):
    def repl(match):
        groups = match.groups()
        if groups[2]:
            return STRING_UNESCAPE_MAP[groups[2]]
        else:
            return unichr(int(groups[0] or groups[1], 16))
    return STRING_ESCAPE_SEQ.sub(repl, string)



class Parser(object):

    def __init__(self, engine, baseiri, strict=False):
        self.reset(engine, baseiri, strict)
        PrefixedName = PNAME_LN | PNAME_NS
        Iri = IRIREF | PrefixedName
        BNode = BLANK_NODE_LABEL | ANON


        RDFLiteral = STRING \
            + Optional(LANGTAG("langtag") | Group(Suppress('^^') + Iri)("datatype"))
        Object = Forward()
        Collection = Suppress('(') + ZeroOrMore(Object) + Suppress(')')
        PredicateObjectList = Forward()
        BlankNodePropertyList = Suppress('[') + PredicateObjectList + \
                                Suppress(']')
        TtlLiteral = RDFLiteral | NUMERIC_LITERAL | BOOLEAN_LITERAL
        Subject = Iri | BNode | Collection \
                  | VARIABLE # added for LD Patch
        Predicate = Iri
        Object << (Iri | BNode | Collection | BlankNodePropertyList | TtlLiteral \
                   | VARIABLE) # added for LD Patch
        Verb = Predicate | Keyword('a')
        ObjectList = Group(Object + ZeroOrMore(COMMA + Object))
        PredicateObjectList << (
            Verb + ObjectList + ZeroOrMore(SEMICOLON +  Optional(Verb + ObjectList)))
        Triples = (Subject + PredicateObjectList) \
                | (BlankNodePropertyList + Optional(PredicateObjectList))

        Value = Iri | TtlLiteral | VARIABLE

        InvPredicate = Suppress('^') + Predicate
        FirstStep = Optional(Suppress('/')) + (Predicate | InvPredicate | INDEX)
        Step = Suppress('/') + (Predicate | InvPredicate | INDEX)
        Filter = Forward()
        Constraint = ( Filter | UNICITY_CONSTRAINT )
        Path = Group((FirstStep | Constraint) + ZeroOrMore(Step | Constraint))
        Filter << (Suppress('[')
            + Group(ZeroOrMore(Step | Constraint))("path") # Path (but copy required for naming)
            + Optional( Suppress('=') + Object )("value")
            + Suppress(']'))

        Graph = Suppress("{") + Triples + ZeroOrMore(PERIOD + Triples) + Optional(PERIOD) + Suppress("}")
        Prefix = Literal("@prefix") + PNAME_NS + IRIREF + PERIOD
        Bind = BIND_CMD + VARIABLE + Value + Optional(Path) + PERIOD
        Add = ADD_CMD + Graph + PERIOD
        Delete = DELETE_CMD + Graph + PERIOD
        UpdateList = UPDATELIST_CMD + Subject + Predicate + SLICE + Collection \
                   + PERIOD

        Statement = Prefix | Bind | Add | Delete | UpdateList
        Patch = ZeroOrMore(Statement)
        Patch.ignore('#' + restOfLine) # Comment
        Patch.parseWithTabs()

        self.grammar = Patch


        IRIREF.setParseAction(self._parse_iri)
        PrefixedName.setParseAction(self._parse_pname)
        RDFLiteral.setParseAction(self._parse_turtleliteral)
        InvPredicate.setParseAction(self._parse_invpredicate)
        Filter.setParseAction(self._parse_filter)
        Path.setParseAction(self._parse_as_list)
        Prefix.setParseAction(self._do_prefix)
        Bind.setParseAction(self._do_bind)
        Add.setParseAction(self._do_add)
        Delete.setParseAction(self._do_delete)
        UpdateList.setParseAction(self._do_updatelist)

        # TODO reorder that
        Verb.setParseAction(self._parse_verb)
        Collection.setParseAction(self._parse_collection)
        ObjectList.setParseAction(self._parse_as_list)
        BlankNodePropertyList.setParseAction(self._parse_bnpl)
        Triples.setParseAction(self._parse_tss)


    def reset(self, engine, baseiri, strict=False):
        self.engine = engine
        self._current_graph = None
        self.baseiri = rdflib.URIRef(baseiri)
        self.strict = strict
        self.in_prologue = True

    def get_current_graph(self, clear=False):
        ret = self._current_graph
        if ret is None:
            self._current_graph = ret = rdflib.Graph()
        if clear:
            self._current_graph = None
        return ret

    def _parse_iri(self, s, loc, toks):
        iri = unescape_iri(toks[0][1:-1])
        return rdflib.URIRef(iri, self.baseiri)

    def _parse_pname(self, s, loc, toks):
        local_name = unescape_local_name(toks.suffix)
        return self.engine.expand_pname(toks.prefix, local_name)

    def _parse_turtleliteral(self, s, loc, toks):
        if toks.langtag:
            langtag = toks.langtag[0]
        else:
            langtag = None
        if toks.datatype:
            datatype = toks.datatype[0]
        else:
            datatype = None
        value = unescape_string(toks[0])
        return rdflib.Literal(value, langtag, datatype)

    def _parse_as_list(self, s, loc, toks):
        return toks.asList()

    def _parse_collection(self, s, loc, toks):
        items = toks.asList()
        if items:
            graph = self.get_current_graph()
            head = rdflib.BNode()
            col = RdfCollection(graph, head, items)
            return head
        else:
            return RDF_NIL


    def _parse_invpredicate(self, s, loc, toks):
        return engine.InvIRI(toks[0])

    def _parse_filter(self, s, loc, toks):
        if toks.value:
            value = toks.value[0]
        else:
            value = None
        return engine.PathConstraint(toks.path.asList(), value)
    
    def _do_prefix(self, *args):
        if self.strict and not self.in_prologue:
            raise ParserError("Prefix declaration can only appear at the "
                              "start (in strict mode)")
        s, loc, toks = args[0], args[1], args[2]
        self.engine.prefix(*toks[1:])

    def _do_bind(self, s, loc, toks):
        self.in_prologue = False
        self.engine.bind(*toks)

    def _do_add(self, s, loc, toks):
        self.in_prologue = False
        assert not toks, toks
        self.engine.add(self.get_current_graph(clear=True))

    def _do_delete(self, s, loc, toks):
        self.in_prologue = False
        assert not toks, toks
        self.engine.delete(self.get_current_graph(clear=True))

    def _do_updatelist(self, s, loc, toks):
        self.in_prologue = False
        self.engine.updatelist(self.get_current_graph(clear=True), *toks)


    # TODO reorder that

    def _parse_bnpl(self, s, loc, toks):
        graph = self.get_current_graph()
        add = graph.add
        subj = rdflib.BNode()
        property_list = iter(toks)
        for pred in property_list:
            objlist = property_list.next()
            for obj in objlist:
                add((subj, pred, obj))
        return subj

    def _parse_tss(self, s, loc, toks):
        graph = self.get_current_graph()
        add = graph.add
        property_list = iter(toks.asList())
        subj = property_list.next()
        for pred in property_list:
            objlist = property_list.next()
            for obj in objlist:
                add((subj, pred, obj))
        return []


    def _parse_verb(self, s, loc, toks):
        if toks[0] == "a":
            return rdflib.RDF.type
        else:
            return toks

    # END TODO



    def parseString(self, txt):
        if type(txt) is str:
            txt = txt.decode("utf8")
        try:
            self.grammar.parseString(txt, True)
        except ParseException, ex:
            raise ParserError(ex)

class ParserError(Exception):
    pass
