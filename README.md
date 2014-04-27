Malang is a (very) minimalistic functional programming language. It's pretty useless, but it was fun to make.

It's made in Python 3 and depends upon Python Lex-Yacc. In Debian (and probably Ubuntu), you can install it with `sudo apt-get install python3-ply`.

Enter this in the shell to start dashing out compound expressions in the REPL:

    $ ./malang.py -i

Here's an example session:

    Malang> 234, 923.
    923
    Malang> [@ * @.] 5.
    25
    Malang> List := #[one, two, three].
    {one, {two, {three, nil}}}
    Malang> Lists:Reverse List.
    {three, {two, {one, nil}}}
    Malang> Bools:And yeah nope.
    nope
    Malang> Ages := #[{peter, 20}, {mary, 22}, {george, 30}].
    {{peter, 20}, {{mary, 22}, {{george, 30}, nil}}}
    Malang> Dicts:Get george Ages.
    {ok, 30}
    Malang> Dicts:Get me Ages.
    sorry
    Malang> Dicts:Set me 123 Ages.
    {{me, 123}, {{peter, 20}, {{mary, 22}, {{george, 30}, nil}}}}
    Malang> Dicts:Remove peter Ages.
    {{mary, 22}, {{george, 30}, nil}}
    Malang> Pairings := #[{P1, P2} | {P1, _} <- Ages, {P2, _} <- Ages, P1 > P2].
    {{peter, mary}, {{peter, george}, {{mary, george}, nil}}}
    Malang> 


It has function scope, closures, modules, tail call elimination, higher order functions and pattern matching.

All functions take exactly 1 argument (but they can take tuples as arguments, and use currying).

All functions are anonymous. Functions are values, and can be bound to a name.

Pattern matching is the only way to bind identifiers to values. You can't 'rebind' an
identifier, once you've said that A := 3, you can't change it. A is 3 always.

The only way to loop is to use recursion and with list comprehensions. The control flow
constructs are 'case of', 'throw/catch' and 'if then else' (plus the filters in list comprehensions).

There are 6 types of values: numbers (only integers), strings, atoms, tuples, functions and modules. Lists are
not a fundamental datatype, they are simply linked lists made up of two-tuples. Dicts are just lists of two-tuples
of the form `{<key>, <val>}`.

Numbers have the syntax `(<base>#)?<number>` where base can be from 2 (for binary)
to 16 (for hexadecimal), and base defaults to 10 (decimal). 
Strings are what you'd expect, like `"string with \" < quote and \\ < backslash "`.
Any character following a backslash is escaped, even if it doesn't have a special meaning like \n and \t,
so "\hay" is the same string as just "hay".
Atoms are tokens that match the regex `[a-z][a-zA-Z0-9_]*`, and are just values that you can use
in your programs (in tuples, et cetera). Identifiers are names which
are bound to values, and they must match the regex `[A-Z_][a-zA-Z0-9_]*`.

Tuples are just... tuples, surrounded by `{` and `}`, like this: `{1, 2, 3}`.

Lists have almost the same syntax as tuples: `#[1, 2, 3]`, however that is just syntactic sugar.
`#[1, 2, 3]` translates into `{1, {2, {3, nil}}}` (where `nil` is an atom).

A Malang program is a list of compound expressions.

A compound expression is 1 or more expression seperated by commas, ending with a dot. For example:

    1, 3 + 1, "hello".

or

    "Hello".

The value of a compound expression is the value of the last expression.

A function is a list of compound expressions surrounded by square brackets. For example:

    [1, 3. 
     {atom, "string"}.]

The above function will always return the tuple `{atom, "string"}`, because functions returns the value
of the last compound expression.

You pattern-match with the 'bind' operator, ":=". Like this


    Three := 3.
    {One, {Two, Three}} := {1, {2, 3}}.

It will evaluate the right side expression and try to match it with the left side pattern (from left to right).
If it sees an unbound identifier (an identifier that hasn't been pattern-matched already)
it will just bind it to the respective value on the right hand side.

This will only match tuples with two identical elements:

    Tuple := {"hay", "hay"}.
    {Same, Same} := Tuple.

Because the second time it sees `Same`, it is no longer an unbound identifier, and malang will insist
that it must match.

The syntax for function application is `<expr> <expr>`.

As I said eariler, all functions take exactly one argument. It is automatically bound to the special
identifier `@`.

Here is factorial written in Malang:

    Factorial := [
      case @ of
        1 -> 1.
        N -> N * Factorial (N-1).
      end.
    ].

The reason i write `Factorial (N-1)` is that function application has higher precedence than arithmetic operations
so `Factorial N-1` would be parsed as `(Factorial N) - 1`, which is not what I wanted.

That version of factorial is not tail recursive, however, and you can't really calculate `Factorial 20000` without
hitting the recursion limit. Here's a tail recursive version:

    Factorial_Tail_Recursive := [
      Helper := [
        {N, Acc} := @.
        case N <= 1 of
          yeah -> Acc.
          nope -> Helper {N-1, N * Acc}.
        end.
      ].
      Helper {@, 1}.
    ].

With that version, you *can* calculate `Factorial 20000`.

The `case of` construct is just like the `:=` operator, except it tries to pattern match on several patterns,
and stops once a pattern matches, and executes the corresponding compound expression. The syntax is

    case <expr> of
      <pattern1> -> <compund_expr1>
      ...
      <patternN> -> <compound_exprN>
    end

You can use the builtin function `Require` to import modules. Like this:

    My_Module := Require "src/module.malang".

It will evaluate the program in the file specified, and then return a module.

'Module access' is used to make use of a module, this is the syntax

    <module>:<expr>

It will evaluate `<expr>` in the context of `<module>`, or in other words, in the same environment, and then return it.
So you can use all the identifiers in the module inside `<expr>`. `<expr>` is usually just an identifier that points to
a function in the module, but it could be a more complicated expression, such as a tuple or a function expression. Why not.

So if `My_Module` contains a function bound to the identifier `Factorial` then you can do this to use it:

    My_Module:Factorial 20000.

It evaluates `Factorial` in the context of `My_Module`, the result of that is a function, and it is then called with the
argument 20000.

The identifier `_` is special, it will match anything and is never bound to anything.


# License

GNU GPLv3
