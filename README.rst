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

    LDPatch ::= ( Bind | Add | Delete | Replace )*
    Bind ::= Var Path
    Add ::= Subject Predicate ( Object | List )
    Delete ::= Subject Predicate Object
    Replace ::= Subject Predicate Slice List

    Subject ::= IRI | Bnode | Var
    Predicate ::= IRI
    Object ::= IRI | BNode | Literal | Var
    List ::= '(' Object* ')'
    Slice ::= Index Index? | "End"

    Path ::= Object Constraint* ( PathElement Constraint* )*
    Constraint ::= PathConstraint | UnicityConstraint
    PathElement ::= Predicate | InvPredicate | Index
    InvPredicate ::= Predicate
    PathConstraint ::= PathElement Constraint* ( PathElement Constraint* )* PathConstraintValue?
    PathConstraintValue ::= Object

    # Terminal Symbols
    IRI                # inherited from RDF concepts
    Literal            # inherited from RDF concepts
    BNode              # inherited from RDF concepts
    Var
    Index              # positive integer
    UnicityConstraint


Concrete Syntax
===============

This concrete syntax uses Turtle for terminal symbols::

    LDPatch ::= ( Bind | Add | Delete | Replace | Prefix | Comment )*
    Bind ::= "Bind" Var Path
    Add ::= "Add" Subject Predicate ( Object | List )
    Delete ::= "Delete" Subject Predicate Object
    Replace ::= "Replace" Subject Predicate Slice List
    Prefix ::= "Prefix" PNAME_NS IRIREF
    Comment ::= "#" [^\n]* "\n"

    Subject ::= IRI | Bnode | Var
    Predicate ::= IRI
    Object ::= IRI | BNode | Literal | Var
    List ::= '(' Object* ')'
    Slice ::= ( Index ( '>' Index? )? ) | '>'
    Index ::= [0-9]+

    Path ::= Object Constraint* ( '/' PathElement Constraint* )*
    Constraint ::= PathConstraint | UnicityConstraint
    PathElement ::= Predicate | InvPredicate | Index
    InvPredicate ::= '-' Predicate
    PathConstraint ::= '[' PathElement Constraint* ( '/' PathElement Constraint* )*  ( '=' Object )? ']'

    IRI               ::= IRIREF | PrefixedName
    Literal           ::= RDFLiteral | NumericLiteral | BooleanLiteral
    BNode             ::= BLANK_NODE_LABEL
    Index             ::= [0-9]+
    Var               ::= (copied from SPARQL)
    UnicityConstraint ::= '!'

    PNAME_NS          ::= (copied from Turtle)
    IRIREF            ::= (copied from Turtle)
    PrefixedName      ::= (copied from Turtle)
    RDFLiteral        ::= (copied from Turtle)
    NumericLiteral    ::= (copied from Turtle)
    BooleanLiteral    ::= (copied from Turtle)
    BLANK_NODE_LABEL  ::= (copied from Turtle)
    PN_CHARS          ::= (copied from Turtle)


Thanks
======

\... to `Alexandre Bertails`_ and `Andrei Sambra`_
for their help on this project.

.. _Alexandre Bertails: http://bertails.org/
.. _Andrei Sambra: http://fcns.eu/
