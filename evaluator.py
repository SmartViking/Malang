#!/usr/bin/env python3
"""
Copyright (C) 2014 Mattias Ugelvik

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from parser import parse
from utils import Env, Node, MalangError
import utils
import operator
import itertools


def eval_list_comprehension(state, expr, emitters, acc):
    """
    This evaluates the list comprehension, and mutates `acc`, which should be
    a python list. `expr` is the expression on the left hand side of the pipe
    in a list comprehension (like #[<expr> | ...]). Emitters is a python tuple
    of `emitters`, which are the things on the right hand side of a list comprehension,
    seperated by commas (like #[<expr> | <emitter1> , <emitter2>, ... <emitterN> ].
    An emitter can either be `filter`, which restricts what goes into the list, or
    or an actual emitter, which is a pattern combined with an expression that
    evaluates to a list, and the pattern is pattern matched with each element of the list
    one at a time.
    """

    emitter = emitters[0]
    last_emitter = len(emitters) <= 1

    if emitter._type == 'filter':
        result = trampoline(emitter.content, state)
        if utils.truthy(result):
            if last_emitter:
                acc.append(trampoline(expr, state))
            else:
                eval_list_comprehension(state, expr, emitters[1:], acc)

    elif emitter._type == 'emitter':
        pattern = emitter.content['pattern']
        value   = trampoline(emitter.content['expr'], state)

        if value._type == 'str':
            items = (Node('str', c) for c in value.content)
        elif value._type == 'list':
            items = utils.generate_items(value)
        elif value._type == 'tuple':
            items = value.content
        elif value._type == 'number':
            items = (Node('number', n) for n in range(1, value.content+1))
        else:
            raise MalangError("Invalid emitter type ({}) in list comprehension".format(value._type), state)

        for item in items:
            temp_state = state.newenv(state.env.shallow_copy())
            patternmatch(pattern, item, temp_state)
            if last_emitter:
                acc.append(trampoline(expr, temp_state))
            else:
                eval_list_comprehension(temp_state, expr, emitters[1:], acc=acc)


def patternmatch(pattern, expr, state):
    """ `expr` should've been evaluated, `pattern` should not yet have been evaluated.
    Keep in mind that syntactially, 'pattern' can be any expression, like a function definition
    or whatever, even though patternmatching only works on simpler things like numbers and tuples.
    """
    make_exception = lambda s: utils.InvalidMatch("Invalid match ({})".format(s), state.newinfonode(pattern))


    if pattern._type == 'uminus' and pattern.content._type == 'number':
        # Special rule for negative numbers, otherwise I wouldn't be able to match
        # them.
        pattern = pattern.content
        pattern.content = -pattern.content


    if pattern._type == 'list-literal':
        return patternmatch(utils.transform_list_literal(pattern.content, infonode=pattern),
                            expr, state)

    elif state.env.is_unbound_identifier(pattern):
        if state.readonly:
            raise MalangError("Cannot bind identifier {!r} in pattern in readonly mode".format(pattern.content),
                              state.newinfonode(pattern))
        else:
            state.env.bind(pattern.content, expr)
            return

    elif pattern._type == 'id' and state.env.is_bound(pattern.content):
        val = state.env.get(pattern.content, state.newinfonode(pattern))
        if not utils.equal(val, expr):
            raise make_exception("identifier {!r} is already bound".format(pattern.content))
        return

    elif pattern._type == 'cons':
        if expr._type != 'list':
            raise make_exception("tried to match something of type {} agains a cons pattern".format(expr._type))
        elif utils.is_nil(expr):
            raise make_exception("tried to match the empty list against a cons pattern")

        patternmatch(pattern.content[0], expr.content[0], state)
        patternmatch(pattern.content[1], expr.content[1], state)
        return

    elif pattern._type == 'module_access':
        module, access = pattern.content
        if not (module._type == 'id' and
                state.env.is_bound(module.content) and
                state.env.get(module.content, state.newinfonode(pattern))._type == 'module'):
            raise MalangError("Invalid module in pattern", state.newinfonode(pattern))
        else:
            return patternmatch(access, expr,
                                state.newenv(
                                    state.env.get(module.content,
                                                  state.newinfonode(pattern)).content).newreadonly(True))


    elif pattern._type != expr._type:
        raise make_exception(
            "tried to match something of type {} agains a pattern of type {}".format(expr._type, pattern._type))

    elif pattern._type == 'list':
        pattern_nil, expr_nil = utils.is_nil(pattern), utils.is_nil(expr)

        if pattern_nil and expr_nil:
            return
        elif pattern_nil or expr_nil:
            if pattern_nil:
                raise make_exception("tried to match a list of 1 or more elements agains the empty list pattern")
            elif expr_nil:
                raise make_exception("tried to match the empty list agains a pattern-list of 1 or more elements")

        patternmatch(pattern.content[0], expr.content[0], state)
        patternmatch(pattern.content[1], expr.content[1], state)
        return


    elif pattern._type == 'tuple':
        pattern_len = len(pattern.content)
        expr_len = len(expr.content)
        if not pattern_len == expr_len:
            raise make_exception(
                "tried to match a tuple of length {} agains a pattern-tuple of length {}".format(expr_len, pattern_len))
        for pat, e in zip(pattern.content, expr.content):
            patternmatch(pat, e, state)
        return

    elif pattern._type in ('number', 'str', 'atom'):
        if not pattern.content == expr.content:
            raise make_exception(
                "tried to match the {} {!r} agains the pattern-{} {!r}".format(expr._type, expr.content,
                                                                               pattern._type, pattern.content))
        return


    raise MalangError("Don't know how to pattern-match that. ", state.newinfonode(pattern))

arithmetic_funcs = {
    'plus':   operator.add,
    'minus':  operator.sub,
    'divide': operator.floordiv,
    'times':  operator.mul,
    'modulo': operator.mod,
    'pow':    operator.pow
}

cmp_funcs = {
    'gt': utils.greater_than,
    'lt': utils.less_than,
    'ge': utils.greater_than_or_eq,
    'le': utils.less_than_or_eq,
    'eq': utils.equal,
    'ne': lambda op1, op2: not utils.equal(op1, op2)
}

def thunk(func, *args, **kwargs):
    def _f():
        return func(*args, **kwargs)
    return _f

def trampoline(expr, state):
    """
    This trampoline function is necessary for the purpose of implementing tail call elimination.
    When `maval' is about to evaluate an expression in tail position, it returns a thunk
    instead of recursing deeper into itself, thus making sure that the python call stack
    doesn't grow huge. So it's like `maval' is 'jumping' on this trampoline. I guess.
    """
    result = maval(expr, state)
    while callable(result):
        result = result()
    return result

def maval(expr, state):
    """
    This is the evaluation function. I didn't want to shadow the python builtin function `eval', so I called it
    `maval' instead. `expr' is the abstract syntax tree that has been created with Python Lex-Yacc.
    `state.env' is an Env instance, storing the identifier bindings for malang. It will be mutated inside `maval'.
    `maval' can return:
    (1) A 'Node' instance, signifying a value, it could for example return Node('number', 3), which could maybe
    be the result of evaluating the expression Node('plus', (Node('number' 2), Node('number', 1))).
    (2) A thunk (i.e. a function meant to be called later, delaying some computation).
    This is used to implement tail call elimination; `maval' can't just naively recurse deeper because python
    itself has no tail call elimination, and python's call stack would explode.
    """

    state = state.newinfonode(expr)

    T = expr._type

    if T in ('number', 'str', 'atom', 'function', 'builtin'):
        return expr

    elif T == 'uminus':
        op = trampoline(expr.content, state)
        if not op._type == 'number':
            raise MalangError("Invalid arithmetic expression", state)
        return Node('number', -op.content, infonode=expr)

    elif T in ('plus', 'minus', 'divide', 'times', 'modulo', 'pow'):

        op1, op2 = (trampoline(op, state) for op in expr.content)
        if op1._type == op2._type:
            _type = op1._type

            if _type == 'number':
                if T in ('modulo', 'divide') and op2.content == 0:
                    raise MalangError("Division or modulo by zero", state)
                else:
                    return Node('number', arithmetic_funcs[T](op1.content, op2.content), infonode=expr)
            elif _type == 'str' and T == 'plus':
                return Node('str', op1.content + op2.content, infonode=expr)
            elif _type == 'tuple' and T == 'plus':
                return Node('tuple', op1.content + op2.content, infonode=expr)
            elif _type == 'list' and T == 'plus':
                return utils.concat_malang_lists(op1, op2)

        elif T == 'times' and {op1._type, op2._type} == {'number', 'str'}:
            return Node('str', op1.content * op2.content)
        elif T == 'times' and {op1._type, op2._type} == {'number', 'tuple'}:
            return Node('tuple', op1.content * op2.content)
        elif T == 'times' and {op1._type, op2._type} == {'number', 'list'}:
            times, malanglist = (op1, op2) if op1._type == 'number' else (op2, op1)

            return utils.concat_malang_lists(*(malanglist for _ in range(times.content)))
        else:
            raise MalangError("Invalid arithmetic expression", state)


    elif T in ('eq', 'ne', 'gt', 'lt', 'ge', 'le'):
        op1, op2 = (trampoline(op, state) for op in expr.content)
        try:
            result = cmp_funcs[T](op1, op2)
        except TypeError:
            raise MalangError("Cannot compare values of types {} and {} with the {} operator"
                              .format(op1._type, op2._type, T),
                              state)
        return Node('atom', {True: 'yeah', False: 'nope'}[result], infonode=expr)

    elif T == 'tuple':
        return Node('tuple', tuple(trampoline(e, state) for e in expr.content), infonode=expr)

    elif T == 'cons':
        head, tail = (trampoline(op, state) for op in expr.content)
        if tail._type == 'list':
            return Node('list', (head, tail))
        else:
            raise MalangError("The second operand to the cons operator has to be a list", state)

    elif T == 'list-literal':
        elems = tuple(trampoline(e, state) for e in expr.content)
        return utils.transform_list_literal(elems, expr)

    elif T == 'list_comprehension':
        result = []
        leftside_expr, emitters = expr.content

        eval_list_comprehension(state, leftside_expr, emitters, acc=result)
        return utils.iter_to_malang_list(result)


    elif T == 'bind':
        pattern, e = expr.content
        val = trampoline(e, state)
        temp_env = state.env.shallow_copy()

        patternmatch(pattern, val, state.newenv(temp_env))

        # copying over the new bindings, after the patternmatch is successful, to avoid
        # 'partial' pattern matching. If I didn't use `temp_evn` in the above call to `patternmatch`
        # then evaluating `{Same, Same} := {23, 11}.` in the REPL would leave the REPL env
        # in an 'inconsistent' state. Using the temporary state means that `Same` will be
        # unbound after that code has been evaluated, because the patternmatch was unsuccessful,
        # raising an exception, thus the code below never executes.
        for name in set(temp_env.bindings) - set(state.env.bindings):
            state.env.bind(name, temp_env.bindings[name])
        return val

    elif T == 'id':
        return state.env.get(expr.content, state)

    elif T == 'module_access':
        module = trampoline(expr.content[0], state)
        if module._type != 'module':
            raise MalangError("You tried to use module access on something that wasn't a module", state)
        val = trampoline(expr.content[1], state.newenv(module.content).newreadonly(True))
        return val

    elif T == 'composition':
        f1, f2 = (trampoline(e, state) for e in expr.content)
        utils.assert_type(f1, ('builtin', 'function'), state)
        utils.assert_type(f2, ('builtin', 'function'), state)

        code = Node('program', [
            Node('program', [
                Node('fncall', (f1,
                                Node('fncall', (f2, Node('id', '@')), infonode=expr)),
                     infonode=expr
                 )
            ])
        ])

        return Node('function', {
            'code': code,
            'filename': state.filename,
            'docstring': None,
            'parent_env': state.env
        })

    elif T == 'fncall':
        func, arg = (trampoline(e, state) for e in expr.content)
        utils.assert_type(func, ('builtin', 'function'), state)
        if func._type == 'builtin':
            return func.content(arg, state)
        elif func._type == 'function':
            return thunk(maval,
                         func.content['code'],
                         state.newenv(
                             Env(parent=func.content['parent_env'], bindings={'@': arg})
                         ).newfilename(
                             func.content['filename']
                         ))

    elif T == 'func_def':
        maybe_docstring = expr.content[0].content[0].content[0]
        if maybe_docstring._type == "str":
            docstring = maybe_docstring.content
        else:
            docstring = None
        return Node('function', {'code': expr.content[0],
                                 'filename': expr.content[1],
                                 'docstring': docstring,
                                 'parent_env': state.env}, infonode=expr)

    elif T == 'program':
        start = expr.content[:-1]
        last  = expr.content[-1]
        for e in start:
            trampoline(e, state)
        return thunk(maval, last, state)

    elif T == 'case_of':
        val = trampoline(expr.content['matched_expr'], state)
        for arrow in expr.content['arrow_sequence']:
            temp_state = state.newenv(Env(parent=state.env))
            try:
                patternmatch(arrow['pattern'], val, temp_state)
            except utils.InvalidMatch:
                continue

            return thunk(maval, arrow['expr'], temp_state)
        raise MalangError("No pattern matched in case_of expression", state)

    elif T == 'if':
        test_expr, if_true, if_false = expr.content
        temp_state = state.newenv(Env(parent=state.env))
        if utils.truthy(trampoline(test_expr, temp_state)):
            return thunk(maval, if_true,  temp_state)
        else:
            return thunk(maval, if_false, temp_state)

    elif T == 'catch':
        try:
            result = trampoline(expr.content, state)
        except MalangError as e:
            return e.args[0]

        return Node('tuple', (Node('atom', 'no_throw'), result))

    elif T == 'throw':
        value = trampoline(expr.content, state)
        raise utils.Throw(value)

    elif T == 'classified':
        exposed, program = expr.content
        hidden_state = state.newenv(Env(parent=state.env))
        result = trampoline(program, hidden_state)

        for ident in exposed:
            val = hidden_state.env.get(ident.content, state)
            state.env.bind(ident.content, val)
        
        return result

    raise MalangError("Unknown expression {!r}".format(utils.AST_to_str(expr)), state)



def call_malang_func(func, arg, state):
    """
    Call the already evaluated `func` with the already evaluated `value`.
    """
    utils.assert_type(func, ('builtin', 'function'), state)
    if func._type == 'builtin':
        return func.content(arg, state.newinfonode(expr))
    elif func._type == 'function':
        return trampoline(func.content['code'],
                          utils.State(env=Env(parent=func.content['parent_env'], bindings={'@': arg}),
                                      filename=func.content['filename']))

