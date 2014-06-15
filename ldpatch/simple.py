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
from pyparsing import And, Combine, Forward, Group, Literal, OneOrMore, Optional, quotedString, Regex, Suppress, ZeroOrMore

import rdflib

import engine


# the following rules are from the SPARQL syntax
# http://www.w3.org/TR/2013/REC-sparql11-query-20130321/

PLX = Regex(r"%[0-9a-fA-F]{2}|\\[_~.\-!$&\'()*+,;=/?#@%]")
PN_CHARS_BASE= Regex(ur'[A-Z]|[a-z]|[\u00C0-\u00D6]|[\u00D8-\u00F6]|[\u00F8-\u02FF]|[\u0370-\u037D]|[\u037F-\u1FFF]|[\u200C-\u200D]|[\u2070-\u218F]|[\u2C00-\u2FEF]|[\u3001-\uD7FF]|[\uF900-\uFDCF]|[\uFDF0-\uFFFD]|[\U00010000-\U000EFFFF]')
PN_CHARS_U = PN_CHARS_BASE | '_'
PN_CHARS = PN_CHARS_U | '-' | Regex(ur'[0-9]|\u00B7|[\u0300-\u036F]|[\u203F-\u2040]')

#    A ( (B|'.')* B )?
# However, these rules do not work as is in PyParsing, which greedily matches B|'.'
# and then fails to match the final B.

#PN_PREFIX = Combine(
#    PN_CHARS_BASE
#    + Optional(ZeroOrMore(PN_CHARS | '.') + PN_CHARS)
#)
#PN_LOCAL = Combine(
#    (PN_CHARS_U | ':' | Regex('[0-9]') | PLX)
#    + Optional(ZeroOrMore(PN_CHARS | '.' | ':' | PLX)
#               + (PN_CHARS | ':' | PLX))
#)("suffix")
#BLANK_NODE_LABEL = Combine(
#    '_:'
#    + ( PN_CHARS_U | Regex('[0-9]') )
#    + Optional(ZeroOrMore(PN_CHARS|'.') + PN_CHARS)
#)

# We replace them with a version allowing '.' at the end,
# which would be a problem in Turtle, but not in LD-Patch anyway.
# So it might be better to find a correct way to implement it in PyParsing,
# or we could live with this approximation...

PN_PREFIX = Combine(PN_CHARS_BASE + ZeroOrMore(PN_CHARS | '.'))("prefix")
PN_LOCAL = Combine(
    (PN_CHARS_U | ':' | Regex('[0-9]') | PLX)
    + ZeroOrMore(PN_CHARS | '.' | ':' | PLX)
)("suffix")

BLANK_NODE_LABEL = Combine(
    '_:'
    + ( PN_CHARS_U | Regex('[0-9]') )
    + ZeroOrMore(PN_CHARS|'.')
)

PNAME_NS = Optional(PN_PREFIX, "") + Suppress(':')
PNAME_LN = Combine(PNAME_NS + PN_LOCAL)
IRIREF = Regex(r'<([^\x00-\x20<>"{}|^`\\]|\u[0-9a-fA-F]{4}|\U[0-9a-fA-F]{8})*>')
STRING = quotedString # TODO implement real Turtle syntax?
LANGTAG = Suppress('@') + Regex(r'[a-zA-Z]+(-[a-zA-Z0-9]+)*')
INTEGER = Regex(r'[+-]?[0-9]+')
DECIMAL = Regex(r'[+-]?[0-9]*\.[0-9]*')
EXPONENT = Regex(r'[eE][+-]?[0-9]+')
DOUBLE = Regex(r'[+-]?[0-9]+\.[0-9]*|[+-]?\.?[0-9]+|[+-]?\.?[0-9]+') + EXPONENT
NUMERIC_LITERAL = DOUBLE | DECIMAL | INTEGER
BOOLEAN_LITERAL = Regex(r'true|false')
ANON = Literal("[") + Literal("]")

# other context-independant rules
VARIABLE = Combine(
    Regex(r'[?$]') + ( PN_CHARS_U | Regex(r'[0-9]') )
    +  ZeroOrMore(PN_CHARS_U | Regex('[0-9\u00B7\u0300-\u036F\u203F-\u2040]'))
)
INDEX = Regex(r'[0-9]+')
UNICITY_CONSTRAINT = Literal('!')
SLICE = ( INDEX + Optional('>' + Optional(INDEX) ) ) | '>'
PERIOD = Suppress(".")


@IRIREF.setParseAction
def parse_iri(s, loc, toks):
    return rdflib.URIRef(toks[0][1:-1])

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
    if toks[0] == '>':
        return engine.Slice(None, '>')
    else:
        return engine.Slice(*toks)

class Parser(object):

    def __init__(self, engine):
        self.reset(engine)
        PrefixedName = PNAME_LN | PNAME_NS
        Iri = IRIREF | PrefixedName
        RDFLiteral = STRING \
            + Optional(LANGTAG("langtag") | Group(Suppress('^^') + Iri)("datatype"))
        PatchLiteral = RDFLiteral | NUMERIC_LITERAL | BOOLEAN_LITERAL
        BNode = BLANK_NODE_LABEL | ANON

        Subject = Iri | BNode | VARIABLE
        Predicate = Iri
        Object = Iri | BNode | PatchLiteral | VARIABLE
        Value = Iri | PatchLiteral | VARIABLE
        List = Group(Suppress('(') + ZeroOrMore(Object) + Suppress(')'))

        InvPredicate = Suppress('-') + Predicate
        Step = Suppress('/') + (Predicate | InvPredicate | INDEX)
        Filter = Forward()
        Constraint = ( Filter | UNICITY_CONSTRAINT )
        Path = Group(ZeroOrMore(Step | Constraint))
        Filter << (Suppress('[')
            + Group(ZeroOrMore(Step | Constraint))("path") # Path (but copy required for naming)
            + Optional( Suppress('=') + Object )("value")
            + Suppress(']'))

        Prefix = Literal("@prefix") + PNAME_NS + IRIREF
        Bind = Literal("Bind") + VARIABLE + Value + Path + PERIOD
        Add = Literal("Add") + Subject + Predicate + (Object | List) + PERIOD
        Delete = Literal("Delete") + Subject + Predicate + Object + PERIOD
        UpdateList = Literal("UpdateList") + Subject + Predicate + SLICE + List + PERIOD

        Statement = Prefix | Bind | Add | Delete | UpdateList
        Comment = Suppress(Regex(r'#[^\n]*\n'))
        Patch = ZeroOrMore(Statement | Comment)

        self.grammar = Patch

        PrefixedName.setParseAction(self._parse_pname)
        RDFLiteral.setParseAction(self._parse_turtleliteral)
        List.setParseAction(self._parse_list)
        InvPredicate.setParseAction(self._parse_invpredicate)
        Filter.setParseAction(self._parse_filter)
        Path.setParseAction(self._parse_list)
        Prefix.setParseAction(self._do_prefix)
        Bind.setParseAction(self._do_bind)
        Add.setParseAction(self._do_add)
        Delete.setParseAction(self._do_delete)
        UpdateList.setParseAction(self._do_updatelist)


    def reset(self, engine):
        self.engine = engine

    def _parse_pname(self, s, loc, toks):
        return self.engine.expand_pname(toks.prefix, toks.suffix)

    def _parse_turtleliteral(self, s, loc, toks):
        if toks.langtag:
            langtag = toks.langtag[0]
        else:
            langtag = None
        if toks.datatype:
            datatype = toks.datatype[0]
        else:
            datatype = None
        return rdflib.Literal(toks[0][1:-1], langtag, datatype)

    def _parse_list(self, s, loc, toks):
        return toks.asList()

    def _parse_invpredicate(self, s, loc, toks):
        return engine.InvIRI(toks[0])

    def _parse_filter(self, s, loc, toks):
        if toks.value:
            value = toks.value[0]
        else:
            value = None
        return engine.PathConstraint(toks.path.asList(), value)
    
    def _do_prefix(self, *args):
        s, loc, toks = args[0], args[1], args[2]
        self.engine.prefix(*toks[1:])

    def _do_bind(self, s, loc, toks):
        self.engine.bind(*toks[1:])

    def _do_add(self, s, loc, toks):
        self.engine.add(*toks[1:])

    def _do_delete(self, s, loc, toks):
        self.engine.delete(*toks[1:])

    def _do_updatelist(self, s, loc, toks):
        self.engine.updatelist(*toks[1:])

    def parseString(self, txt):
        self.grammar.parseString(txt, True)


# for temporary testing
from ldpatch.engine import PatchEngine
g = rdflib.Graph()
e = PatchEngine(g, init_ns={"xsd": rdflib.XSD})
p = Parser(e)
