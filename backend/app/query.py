"""Small datastore query specifications shared by domain services.

These are Python expressions, never SQL. The Firestore repository pushes a
tenant/equality filter to Firestore and evaluates the remaining predicates and
aggregates over that complete scope. This keeps totals exact without requiring
an index for every combination of dashboard filters.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import ClassVar


class DatabaseError(RuntimeError):
    pass


class IntegrityError(DatabaseError):
    pass


class ConcurrentWrite(DatabaseError):
    pass


def value(expr, row):
    return expr.evaluate(row) if isinstance(expr, Expr) else expr


class Expr:
    __hash__ = object.__hash__

    def __init__(self, op, *args):
        self.op, self.args = op, args

    def __eq__(self, other):
        return Expr("eq", self, other)

    def __ne__(self, other):
        return Expr("ne", self, other)

    def __lt__(self, other):
        return Expr("lt", self, other)

    def __le__(self, other):
        return Expr("le", self, other)

    def __gt__(self, other):
        return Expr("gt", self, other)

    def __ge__(self, other):
        return Expr("ge", self, other)

    def __add__(self, other):
        return Expr("add", self, other)

    def __sub__(self, other):
        return Expr("sub", self, other)

    def __invert__(self):
        return Expr("not", self)

    def is_(self, other):
        return self == other

    def is_not(self, other):
        return self != other

    def in_(self, values):
        return Expr("in", self, tuple(values))

    def desc(self):
        return Order(self, True)

    def asc(self):
        return Order(self, False)

    def evaluate(self, row):
        args = [value(a, row) for a in self.args]
        if self.op == "and":
            return all(args)
        if self.op == "or":
            return any(args)
        if self.op == "not":
            return not args[0]
        if self.op == "eq":
            return args[0] == args[1]
        if self.op == "ne":
            return args[0] != args[1]
        if self.op == "in":
            return args[0] in args[1]
        if self.op in {"lt", "le", "gt", "ge"}:
            if args[0] is None or args[1] is None:
                return False
            return {
                "lt": lambda: args[0] < args[1],
                "le": lambda: args[0] <= args[1],
                "gt": lambda: args[0] > args[1],
                "ge": lambda: args[0] >= args[1],
            }[self.op]()
        if self.op == "add":
            return args[0] + args[1]
        if self.op == "sub":
            return args[0] - args[1]
        if self.op == "lower":
            return args[0].lower()
        if self.op == "trim":
            return args[0].strip()
        if self.op == "case":
            return args[1] if args[0] else args[2]
        raise ValueError(f"Unsupported datastore expression: {self.op}")

    def aggregate(self, rows):
        if self.op == "count":
            return len(rows)
        if self.op == "sum":
            return sum(value(self.args[0], row) or 0 for row in rows) if rows else None
        if self.op == "coalesce":
            for arg in self.args:
                result = arg.aggregate(rows) if isinstance(arg, Expr) else arg
                if result is not None:
                    return result
            return None
        return self.evaluate(rows[0]) if rows else None


class Field(Expr):
    def __init__(self, *, default=None, nullable=False, kind="str"):
        super().__init__("field")
        self.default, self.nullable, self.kind = default, nullable, kind

    def __set_name__(self, owner, name):
        self.owner, self.name = owner, name

    def __get__(self, obj, owner=None):
        return self if obj is None else obj.__dict__.get(self.name)

    def __set__(self, obj, val):
        if isinstance(val, datetime) and val.tzinfo is None:
            val = val.replace(tzinfo=UTC)
        if self.kind.startswith("date ") and isinstance(val, str):
            val = date.fromisoformat(val)
        obj.__dict__[self.name] = val

    def evaluate(self, row):
        return getattr(row, self.name)


class Record:
    registry: ClassVar[dict] = {}
    __unique__: ClassVar[list] = []
    __references__: ClassVar[dict] = {}

    def __init_subclass__(cls):
        cls.__fields__ = {k: v for k, v in cls.__dict__.items() if isinstance(v, Field)}
        Record.registry[cls.__collection__] = cls

    def __init__(self, **values):
        unknown = set(values) - self.__fields__.keys()
        if unknown:
            raise TypeError(f"Unknown record fields: {sorted(unknown)}")
        for name, field in self.__fields__.items():
            default = (
                field.default() if callable(field.default) else deepcopy(field.default)
            )
            setattr(self, name, values.get(name, default))

    def to_dict(self):
        return {name: deepcopy(getattr(self, name)) for name in self.__fields__}


class Order:
    def __init__(self, expr, reverse=False):
        self.expr, self.reverse = expr, reverse


class Functions:
    def __getattr__(self, op):
        return lambda *args: Expr(op, *args)


func = Functions()


def and_(*args):
    return Expr("and", *args)


def or_(*args):
    return Expr("or", *args)


def case(pair, *, else_=None):
    return Expr("case", *pair, else_)


def model_of(expr):
    if isinstance(expr, type) and issubclass(expr, Record):
        return expr
    if isinstance(expr, Field):
        return expr.owner
    if isinstance(expr, Expr):
        for arg in expr.args:
            result = model_of(arg)
            if result:
                return result
    return None


class Query:
    def __init__(self, operation, *columns):
        self.operation, self.columns = operation, columns
        self.model = next((m for c in columns if (m := model_of(c))), None)
        self.conditions, self.order, self.groups = [], [], []
        self.cap, self.changes, self.returned = None, {}, []

    def where(self, *conditions):
        self.conditions.extend(conditions)
        return self

    def select_from(self, model):
        self.model = model
        return self

    def order_by(self, *order):
        self.order.extend(order)
        return self

    def group_by(self, *groups):
        self.groups.extend(groups)
        return self

    def limit(self, cap):
        self.cap = cap
        return self

    def values(self, **changes):
        self.changes = changes
        return self

    def returning(self, *fields):
        self.returned = fields
        return self

    def with_for_update(self, **_):
        return self  # repository commit validates all reads

    def matches(self, row):
        return all(value(c, row) for c in self.conditions)


def select(*columns):
    return Query("select", *columns)


def update(model):
    return Query("update", model)


def delete(model):
    return Query("delete", model)


class Result:
    def __init__(self, rows=(), rowcount=None):
        self.rows = list(rows)
        self.rowcount = len(self.rows) if rowcount is None else rowcount

    def __iter__(self):
        return iter(self.rows)

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def one(self):
        if len(self.rows) != 1:
            raise DatabaseError("Expected one result")
        return self.rows[0]

    def scalar_one(self):
        row = self.one()
        return row[0] if isinstance(row, tuple) else row

    def scalar_one_or_none(self):
        return self.scalar_one() if self.rows else None

    def scalar(self):
        row = self.first()
        return row[0] if isinstance(row, tuple) else row


def project(query, rows):
    for order in reversed(query.order):
        order = order if isinstance(order, Order) else Order(order)
        rows.sort(
            key=lambda r: (value(order.expr, r) is not None, value(order.expr, r)),
            reverse=order.reverse,
        )
    if query.groups:
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(value(g, row) for g in query.groups)].append(row)
        result = [
            tuple(c.aggregate(group) for c in query.columns)
            for group in groups.values()
        ]
    elif any(
        isinstance(c, Expr) and c.op in {"sum", "count", "coalesce"}
        for c in query.columns
    ):
        result = [tuple(c.aggregate(rows) for c in query.columns)]
    elif len(query.columns) == 1 and isinstance(query.columns[0], type):
        result = rows
    else:
        result = [tuple(value(c, row) for c in query.columns) for row in rows]
    return Result(result[: query.cap] if query.cap is not None else result)
