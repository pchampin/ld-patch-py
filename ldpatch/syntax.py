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

# pylint: disable=C0103,W0142,W0201

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
from pyparsing import Combine, Forward, Group, Keyword, Literal, OneOrMore, \
    Optional, ParseException, Regex, restOfLine, Suppress, ZeroOrMore
from re import compile as regex, VERBOSE

import rdflib
from rdflib.collection import Collection as RdfCollection

from ldpatch.processor import InvIRI, Slice, PathConstraint, \
    UNICITY_CONSTRAINT as PARSED_UNICITY_CONSTRAINT, Variable

RDF_NIL = rdflib.RDF.nil

# the following rules are from the SPARQL syntax
# http://www.w3.org/TR/2013/REC-sparql11-query-20130321/

PLX = Regex(r"%[0-9a-fA-F]{2}|\\[_~.\-!$&\'()*+,;=/?#@%]")
PN_CHARS_BASE= Regex(ur'[A-Z]|[a-z]|[\u00C0-\u00D6]|[\u00D8-\u00F6]|'
                     ur'[\u00F8-\u02FF]|[\u0370-\u037D]|[\u037F-\u1FFF]|'
                     ur'[\u200C-\u200D]|[\u2070-\u218F]|[\u2C00-\u2FEF]|'
                     ur'[\u3001-\uD7FF]|[\uF900-\uFDCF]|[\uFDF0-\uFFFD]|'
                     ur'[\U00010000-\U000EFFFF]')
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
STRING_LITERAL_QUOTE = Combine(
    Suppress('"') +
    ZeroOrMore(Regex(r'[^\x22\x5C\x0A\x0D]') | ECHAR | UCHAR) +
    Suppress('"'))
STRING_LITERAL_SINGLE_QUOTE = Combine(
    Suppress("'") +
    ZeroOrMore(Regex(r'[^\x27\x5C\x0A\x0D]') | ECHAR | UCHAR) +
    Suppress("'"))
STRING_LITERAL_LONG_SINGLE_QUOTE = Combine(
    Suppress("'''") +
    ZeroOrMore(Regex(r"'{0,2}") + (Regex(r"[^'\\]") | ECHAR | UCHAR)) +
    Suppress("'''"))
STRING_LITERAL_LONG_QUOTE = Combine(
    Suppress('"""') +
    ZeroOrMore(Regex(r'"{0,2}') + (Regex(r'[^"\\]') | ECHAR | UCHAR)) +
    Suppress('"""'))
STRING = (
    STRING_LITERAL_LONG_SINGLE_QUOTE |
    STRING_LITERAL_LONG_QUOTE |
    STRING_LITERAL_QUOTE |
    STRING_LITERAL_SINGLE_QUOTE)
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
INDEX = Regex(r'-?[0-9]+')
UNICITY_CONSTRAINT = Literal('!')
SLICE = INDEX + Optional('..' + Optional(INDEX) ) | '..'
COMMA = Suppress(",")
SEMICOLON = Suppress(";")
PERIOD = Suppress(".")
BIND_CMD = Suppress(Literal("Bind") | Literal("B"))
ADD_CMD = Suppress(Literal("Add") | Literal("A"))
ADDNEW_CMD = Suppress(Literal("AddNew") | Literal("AN"))
DELETE_CMD = Suppress(Literal("Delete") | Literal("D"))
DELETEEXISTING_CMD = Suppress(Literal("DeleteExisting") | Literal("DE"))
CUT_CMD = Suppress(Literal("Cut") | Literal("C"))
UPDATELIST_CMD = Suppress(Literal("UpdateList") | Literal("UL"))


@BLANK_NODE_LABEL.setParseAction
def parse_bnode(s, loc, toks):
    # pylint: disable=C0111,W0613
    return rdflib.BNode(toks[0][2:])

@ANON.setParseAction
def parse_bnode_anon(s, loc, toks):
    # pylint: disable=C0111,W0613
    return rdflib.BNode()

@INTEGER.setParseAction
def parse_integer(s, loc, toks):
    # pylint: disable=C0111,W0613
    return rdflib.Literal(toks[0], datatype=rdflib.XSD.integer)

@DECIMAL.setParseAction
def parse_decimal(s, loc, toks):
    # pylint: disable=C0111,W0613
    return rdflib.Literal(toks[0], datatype=rdflib.XSD.decimal)

@DOUBLE.setParseAction
def parse_double(s, loc, toks):
    # pylint: disable=C0111,W0613
    return rdflib.Literal(u"".join(toks), datatype=rdflib.XSD.double)

@BOOLEAN_LITERAL.setParseAction
def parse_boolean(s, loc, toks):
    # pylint: disable=C0111,W0613
    return rdflib.Literal(toks[0], datatype=rdflib.XSD.boolean)

@VARIABLE.setParseAction
def parse_variable(s, loc, toks):
    # pylint: disable=C0111,W0613
    return Variable(toks[0][1:])

@INDEX.setParseAction
def parse_index(s, loc, toks):
    # pylint: disable=C0111,W0613
    return int(toks[0])

@UNICITY_CONSTRAINT.setParseAction
def parse_unicityconstraint(s, loc, toks):
    # pylint: disable=C0111,W0613
    return PARSED_UNICITY_CONSTRAINT

@SLICE.setParseAction
def parse_slice(s, loc, toks):
    # pylint: disable=C0111,W0613
    if toks[0] == '..':   # ".."
        return Slice(None, None)
    elif len(toks) == 1:  # <index>
        return Slice(toks[0], toks[0]+1)
    elif len(toks) == 2:  # <index> ".."
        return Slice(toks[0], None)
    else:                 # <index> ".." <index>
        return Slice(toks[0], toks[2])


# unescaping
IRI_ESCAPE_SEQ = regex(ur"\\u([0-9A-Fa-f]{4}) | \\U([0-9A-Fa-f]{8})", VERBOSE)
LOCAL_ESCAPE_SEQ = regex(ur"\\([_~.\-!$&'()*+,;=/?#@%])", VERBOSE)
STRING_ESCAPE_SEQ = regex(ur"\\u([0-9A-Fa-f]{4}) | \\U([0-9A-Fa-f]{8}) "
                          ur" | \\([tbnrf\\\"'])", VERBOSE)
STRING_UNESCAPE_MAP = { "t": "\t", "b": "\b", "n": "\n", "r": "\r", "f": "\f",
                        "\\": "\\", '"': '"', "'": "'" }

def unescape_iri(iri):
    """Remove all escaping sequences from IRI"""
    def repl(match):
        """Replace match by the corresponding unicode character"""
        groups = match.groups()
        return unichr(int(groups[0] or groups[1], 16))
    return IRI_ESCAPE_SEQ.sub(repl, iri)

def unescape_local_name(local):
    """Remove all escaping sequences from local name"""
    return LOCAL_ESCAPE_SEQ.sub(r"\1", local)

def unescape_string(string):
    """Remove all escaping sequences from string"""
    def repl(match):
        """Replace match by the corresponding unicode character"""
        groups = match.groups()
        if groups[2]:
            return STRING_UNESCAPE_MAP[groups[2]]
        else:
            return unichr(int(groups[0] or groups[1], 16))
    return STRING_ESCAPE_SEQ.sub(repl, string)



class Parser(object):
    """
    An LD Patch parser.

    Arguments:
    * ``processor``: an LD Patch processor used
    * ``baseiri``: the base IRI used to resolve relative IRIs in the patch
    * ``strict``: an optional flag to enable strict-mode
      (by default, the parser will be more tolerant than the specification,
      see below)

    In non-strict mode:
    * prefix declaration can occur anywhere in the LD Patch document
    * empty graphs are allowed in Add[New]/Delete[Existing]
    """

    def __init__(self, processor, baseiri, strict=False):
        """
        See class docstring.
        """
        # pylint: disable=R0914,R0915
        self.reset(processor, baseiri, strict)
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
        Object << ( # pylint: disable=W0104
            Iri | BNode | Collection | BlankNodePropertyList | TtlLiteral
            | VARIABLE) # added for LD Patch
        Verb = Predicate | Keyword('a')
        ObjectList = Group(Object + ZeroOrMore(COMMA + Object))
        PredicateObjectList << ( # pylint: disable=W0106
            Verb + ObjectList + ZeroOrMore(SEMICOLON +  Optional(Verb + ObjectList)))
        Triples = (Subject + PredicateObjectList) \
                | (BlankNodePropertyList + Optional(PredicateObjectList))

        Value = Iri | TtlLiteral | VARIABLE

        InvPredicate = Suppress('^') + Predicate
        Step = Suppress('/') + (Predicate | InvPredicate | INDEX)
        Filter = Forward()
        Constraint = ( Filter | UNICITY_CONSTRAINT )
        Path = Group(OneOrMore(Step | Constraint))
        Filter << (Suppress('[')  # pylint: disable=W0106
                   + Group(ZeroOrMore(Step | Constraint))("path") # = Path (*)
                   + Optional( Suppress('=') + Object )("value")
                   + Suppress(']'))
                   # (*) we can not reuse the Path rule defined above,
                   #     because we want to set a name for that component

        Graph = (Suppress("{") +
                 Optional(
                     Triples + ZeroOrMore(PERIOD + Triples) + Optional(PERIOD)
                 ) +
                 Suppress("}"))
        Prefix = Literal("@prefix") + PNAME_NS + IRIREF + PERIOD
        Bind = BIND_CMD + VARIABLE + Value + Optional(Path) + PERIOD
        Add = ADD_CMD + Graph + PERIOD
        AddNew = ADDNEW_CMD + Graph + PERIOD
        Delete = DELETE_CMD + Graph + PERIOD
        DeleteExisting = DELETEEXISTING_CMD + Graph + PERIOD
        Cut = CUT_CMD + VARIABLE + PERIOD
        UpdateList = UPDATELIST_CMD + Subject + Predicate + SLICE + Collection \
                   + PERIOD

        Statement = Prefix | Bind | Add | AddNew | Delete | DeleteExisting | Cut | UpdateList
        Patch = ZeroOrMore(Statement)
        Patch.ignore('#' + restOfLine) # Comment
        Patch.parseWithTabs()

        self.grammar = Patch


        IRIREF.setParseAction(self._parse_iri)
        PrefixedName.setParseAction(self._parse_pname)
        RDFLiteral.setParseAction(self._parse_turtleliteral)
        Collection.setParseAction(self._parse_collection)
        BlankNodePropertyList.setParseAction(self._parse_bnpl)
        Verb.setParseAction(self._parse_verb)
        ObjectList.setParseAction(self._parse_as_list)
        Triples.setParseAction(self._parse_tss)
        InvPredicate.setParseAction(self._parse_invpredicate)
        Filter.setParseAction(self._parse_filter)
        Path.setParseAction(self._parse_as_list)
        Prefix.setParseAction(self._do_prefix)
        Bind.setParseAction(self._do_bind)
        Add.setParseAction(self._do_add)
        AddNew.setParseAction(self._do_add_new)
        Delete.setParseAction(self._do_delete)
        DeleteExisting.setParseAction(self._do_delete_existing)
        Cut.setParseAction(self._do_cut)
        UpdateList.setParseAction(self._do_updatelist)


    def reset(self, processor, baseiri, strict=False):
        """Reset this parser to a fresh state"""
        self.processor = processor
        self._current_graph = None
        self.baseiri = rdflib.URIRef(baseiri)
        self.strict = strict
        self.in_prologue = True

    def get_current_graph(self, clear=False, check_empty=False):
        """Return the current graph, creating it if needed"""
        ret = self._current_graph
        if ret is None:
            self._current_graph = ret = rdflib.Graph()
        if clear:
            self._current_graph = None
        if check_empty and len(ret) == 0:
            if self.strict:
                raise ParserError("Empty graph")
        return ret


    def _parse_iri(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        iri = unescape_iri(toks[0][1:-1])
        return rdflib.URIRef(iri, self.baseiri)

    def _parse_pname(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        local_name = unescape_local_name(toks.suffix)
        return self.processor.expand_pname(toks.prefix, local_name)

    @staticmethod
    def _parse_turtleliteral(s, loc, toks):
        # pylint: disable=C0111,W0613
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

    def _parse_collection(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        items = toks.asList()
        if items:
            graph = self.get_current_graph()
            head = rdflib.BNode()
            _ = RdfCollection(graph, head, items)
            return head
        else:
            return RDF_NIL

    def _parse_bnpl(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        graph = self.get_current_graph()
        add = graph.add
        subj = rdflib.BNode()
        property_list = iter(toks)
        for pred in property_list:
            objlist = property_list.next()
            for obj in objlist:
                add((subj, pred, obj))
        return subj

    @staticmethod
    def _parse_verb(s, loc, toks):
        # pylint: disable=C0111,W0613
        if toks[0] == "a":
            return rdflib.RDF.type
        else:
            return toks

    @staticmethod
    def _parse_as_list(s, loc, toks):
        # pylint: disable=C0111,W0613
        return toks.asList()

    def _parse_tss(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        graph = self.get_current_graph()
        add = graph.add
        property_list = iter(toks.asList())
        subj = property_list.next()
        for pred in property_list:
            objlist = property_list.next()
            for obj in objlist:
                add((subj, pred, obj))
        return []

    @staticmethod
    def _parse_invpredicate(s, loc, toks):
        # pylint: disable=C0111,W0613
        return InvIRI(toks[0])

    @staticmethod
    def _parse_filter(s, loc, toks):
        # pylint: disable=C0111,W0613
        if toks.value:
            value = toks.value[0]
        else:
            value = None
        return PathConstraint(toks.path.asList(), value)

    def _do_prefix(self, *args):
        # pylint: disable=C0111,W0613
        if self.strict and not self.in_prologue:
            raise ParserError("Prefix declaration can only appear at the "
                              "start (in strict mode)")
        _, _, toks = args[0], args[1], args[2]
        self.processor.prefix(*toks[1:])

    def _do_bind(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        self.in_prologue = False
        self.processor.bind(*toks)

    def _do_add(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        try:
            self.in_prologue = False
            assert not toks, toks
            self.processor.add(
                self.get_current_graph(clear=True, check_empty=True),
                addnew=False)
        except TypeError, ex:
            raise Exception(ex)

    def _do_add_new(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        self.in_prologue = False
        assert not toks, toks
        self.processor.add(
            self.get_current_graph(clear=True, check_empty=True),
            addnew=True)

    def _do_delete(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        self.in_prologue = False
        assert not toks, toks
        self.processor.delete(
            self.get_current_graph(clear=True, check_empty=True),
            delex=False)

    def _do_delete_existing(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        self.in_prologue = False
        assert not toks, toks
        self.processor.delete(
            self.get_current_graph(clear=True, check_empty=True),
            delex=True)

    def _do_cut(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        self.in_prologue = False
        assert len(toks) == 1
        self.processor.cut(toks[0])

    def _do_updatelist(self, s, loc, toks):
        # pylint: disable=C0111,W0613
        self.in_prologue = False
        self.processor.updatelist(self.get_current_graph(clear=True), *toks)


    def parseString(self, txt):
        """Parse txt as an LD Patch and apply it"""
        if type(txt) is str:
            txt = txt.decode("utf8")
        try:
            self.grammar.parseString(txt, True)
        except ParseException, ex:
            raise ParserError(ex)

class ParserError(Exception):
    """Subclass of all errors raised by the LD Patch parser"""
    pass
