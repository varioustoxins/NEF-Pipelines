from collections.abc import MutableSet
from dataclasses import dataclass
from typing import Optional, Union


class IdentitySet(MutableSet):
    """
    A set that stores object by there identity
    """

    key = id  # should return a hashable object

    def __init__(self, iterable=()):
        self.map = {}  # id -> object
        self |= iterable  # add elements from iterable to the set (union)

    def __len__(self):  # Sized
        return len(self.map)

    def __iter__(self):  # Iterable
        return iter(self.map.values())

    def __contains__(self, x):  # Container
        return self.key(x) in self.map

    def add(self, value):  # MutableSet
        """Add an element."""
        self.map[self.key(value)] = value

    def discard(self, value):  # MutableSet
        """Remove an element.  Do not raise an exception if absent."""
        self.map.pop(self.key(value), None)

    def update(self, iterable):
        for elem in iterable:
            self.add(elem)

    def __repr__(self):
        if not self:
            return "%s()" % (self.__class__.__name__,)
        return "%s(%r)" % (self.__class__.__name__, list(self))


def return_path_and_value(iterable, item):
    return iter.get_path(item), item.value


def return_entity(iter, item):
    return item


def item_only(iter, item):
    return item


def object_children(target, parent):
    result = ()

    if hasattr(target, "model_fields"):
        result = tuple(
            [
                ObjectIter.Entry(target, field_name, getattr(target, field_name))
                for field_name in target.model_fields.keys()
            ]
        )

    elif isinstance(target, list):
        result = tuple(
            [ObjectIter.Entry(target, i, elem) for i, elem in enumerate(target)]
        )

    elif isinstance(target, dict):
        result = tuple(
            [ObjectIter.Entry(target, key, value) for key, value in target.items()]
        )

    return result


class ObjectIter:
    @dataclass
    class Entry:
        target: object
        selector: Optional[Union[int, str]]
        value: object
        is_leaf: bool = False

        def is_root(self):
            return self.target is None and self.selector is None and self.value is None

    def __init__(
        self, child_lister=object_children, result_generator=return_path_and_value
    ):
        self._child_lister = child_lister
        self._result_generator = result_generator
        self._child_parent = ObjectIter.Parents()

    class Parents:
        def __init__(self):
            self._parents = {}

        def add(self, child_info, parent):

            self._parents[id(child_info)] = parent

        def add_all(self, children_info, parent):
            for child_info in children_info:
                self.add(child_info, parent)

        def parent(self, child):
            child_id = id(child)
            return self._parents[child_id] if child_id in self._parents.keys() else None

        def get_path(self, child):

            result = []
            target = child

            while not target.is_root():
                result.append(target.selector)
                target = self.parent(target)

            return tuple(reversed(result[1:]))

    def get_path(self, item):
        return self._child_parent.get_path(item)

    def get_parent(self, item):

        return self._child_parent.parent(item)

    def iter(self, target):

        root_entry = ObjectIter.Entry(None, None, None)
        entry = ObjectIter.Entry(None, None, target)
        self._child_parent.add(entry, root_entry)

        yield self._result_generator(self, entry)

        visited = IdentitySet()
        non_visited = IdentitySet()

        children = self._child_lister(target, root_entry)
        self._child_parent.add_all(children, entry)

        non_visited.update(children)

        while non_visited:
            item = non_visited.pop()

            if item in visited:
                continue

            visited.add(item)

            yield self._result_generator(self, item)

            children = [
                elem
                for elem in self._child_lister(item.value, item)
                if not elem.is_leaf
            ]
            self._child_parent.add_all(children, item)

            non_visited.update(children)
