===========
 RDF-PATCH
===========

This project aims at implementing patch format for Linked Data,
originally based on RDF-Patch_ proposal.

It aims at being able to cope with most RDF graph
without relying on bnode identifiers.
  
.. _RDF-Patch: http://afs.github.io/rdf-patch/

Abstract syntax
===============

For the moment, it only implements an abstract syntax,
which should be equivalent to this::

    LDPatch ::= List(Statement)
    Statement ::= Prefix | Bind | Add | Delete | Replace
    Prefix ::= PNAME_NS IRIREF
    Bind ::= Var Path
    Add ::= Subject Predicate ( Object | List )
    Delete ::= Subject Predicate Object
    Replace ::= Subject Predicate Slice List

    Subject ::= IRIREF | PrefixedName | BLANK_NODE_LABEL | Var
    Predicate ::= IRIREF | PrefixedName
    Object ::= IRIREF | PrefixedName | BLANK_NODE_LABEL | Literal | Var
    List ::= '(' Object* ')'
    Slice ::= ( Index ( '>' Index? )? ) | '>'

    Var = '?' PN_CHARS+
    Literal ::= (to decide: Turtle or N-Triple? -- or JSON?)
    Index ::= [0-9]+

    Path ::= Object Constraint* ( '/' PathElement Constraint* )*
    Constraint = PathConstraint | UnicityConstraint
    PathElement = Predicate | InvPredicate | Index
    InvPredicate ::= '-' Predicate
    PathConstraint = '[' PathElement Constraint* ( '/' PathElement Constraint* )*  ( '=' Object )? ']'
    UnicityConstraint = '!'

    PNAME_NS         ::= (get from Turtle)
    IRIREF           ::= (get from Turtle)
    PrefixedName     ::= (get from Turtle)
    BLANK_NODE_LABEL ::= (get from Turtle)
    PN_CHARS         ::= (get from Turtle)

Thanks
======

\... to `Alexandre Bertails`_ and `Andrei Sambra`_
for their help on this project.

.. _Alexandre Bertails: http://bertails.org/
.. _Andrei Sambra: http://fcns.eu/
