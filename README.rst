===========
 RDF-PATCH
===========

This is project implements an extension of the RDF-Patch_ proposal.
It aims at being able to cope with most RDF graph
without relying on bnode identifiers.

Compared to the original proposals, this implementation supports:

* property paths: the property components of every row can be
  a slash ('/') separated list of elements, where an element is an IRI
  optionnally preceded by the minus symbol ('-').

  A property path instructs the engine to traverse the graph
  from the "subject" node, following arcs of the corresponding predicate
  -- minused predicates should be traversed backward.
  The last arc is the one affected by the command.

  It is expected that a property path matches exactly one path in the graph
  (see Future plans below). 

* list shortcuts: elements in a property path (see aboce) can be followed by
  zero or more *indices* (integer in square brackets).
  Those are shortcut to access values in well-formed RDF collections.

  For example, ``<p>[2]`` is a shortcut for
  ``<p>/<rdf:rest>/<rdf:rest>/<rdf:first>``
  (replacing qnames with the appropriate URI).

  Note that all commands (exept R(eplace), see below) refuse to handle
  a property path *ending* with an index,
  as this would result make the collection ill-formed.

* additional commands: in addition to the original A(dd) and D(elete) commands,
  this implementation introduces to new commands:

  + C(lear) expects a subject and a property path (plus an optional graph name)
    but no object, and removes all matching arcs (regardless of their object).
    Contrarily to D(elete), it can suppress more than one arc
    (but all with the same subject and predicate).

  + R(eplace) expects a subject, property path and object
    (plus an optional graph name)
    and replace the current value of the matching subject-predicate
    with the provided object.
    Contrarily to C(lear), R(eplace) assumes

* list modifications: the R(eplace) command (see above)
  accepts an additional syntax for property paths:

  + R(eplace) can handle a property path ending with an index,
    as it keeps the well-formedness of the collection;

  + R(eplace) also accept a property path ending with a *slice*,
    composed of two integers separated by a colon, enclosed in square brackets
    identifying a sublist of the RDF collection (*alla* Python).

    In that case, the object must be a Turtle list;
    this list can have a different number of elements than the slice;
    this can be used to remove elements, insert elements,
    or empty a list completely.
  
.. _RDF-Patch: http://afs.github.io/rdf-patch/

Installing
==========

For the moment, patch.py is a standalone script;
it requires rdflib v4.0 to be installed.

It can be used as a library (import the Patch class)
or as a standalone command (takes a turtle file as argument,
reads a patch on stdin and writes the resulting turtle on stdout).

Future plans
============

Optimizing path predicates
++++++++++++++++++++++++++

At the moment, a patch like::

  A <s> <p>/<q>/<r>/<s> <o1>.
  A R   R               <o2>.

will be handled sub-optimally,
as the path predicate will be traversed for *each* line.
A smarter implementation would cache the result of the traversal
(the *effective* subject).

The problem comes from the optionnal 4th component, the graph name.
Indeed, this optimization can be used only
if subject and predicate are repeated, *and* if the graph is the same.
That latter condition is not trivial to check, as it might be either
that the graph is also explicitly repeated,
*or* that both lines use the default graph.

Variables
+++++++++

The language would be made more expressive if variables were introduced.
For example::

  B <s> <p> ?v1 .
  D <s> <p> ?v1 .
  A <s> <q> ?v1 .
  A <s> <p> <o> ?v1 .

B stands for "bind", and binds the variable ``?v1`` to the value of the triple,
where the predicate could be arbitrarily complex.
This variable can then be reused multiple times.
Furthermore, the variable can be bound to a blank node,
and make this blank node addressable at places where
it could not have been addressed otherwhise
(object position or graph position).

Multiple updates
++++++++++++++++

Property paths are currently expected to unambiguously identify one arc
(or, for the C command, a set of arc with *same* subject).
This constraint make it more similar to the original proposal
(where each command is affecting at most one arc)
and to prevent a patch to have unexpected effects on a modified graph.

However, sometimes the intention is to modifify *all* nodes matching the path;
it could be interesting to have a variant of each command
allowing property paths to have multiple matches.
