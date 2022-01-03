import functools
import inspect
import json
import logging

from collections import defaultdict
from typing import Callable, Dict

from protean.container import BaseContainer, EventedMixin, OptionsMixin
from protean.exceptions import IncorrectUsageError
from protean.fields import Field
from protean.reflection import _ID_FIELD_NAME, fields, id_field
from protean.utils import (
    DomainObjects,
    derive_element_class,
    fully_qualified_name,
    inflection,
)

logger = logging.getLogger("protean.event")


class BaseEventSourcedAggregate(EventedMixin, OptionsMixin, BaseContainer):
    """Base Event Sourced Aggregate class that all EventSourced Aggregates should inherit from."""

    element_type = DomainObjects.EVENT_SOURCED_AGGREGATE

    class Meta:
        abstract = True

    @classmethod
    def _default_options(cls):
        return [
            ("stream_name", inflection.underscore(cls.__name__)),
        ]

    def __init_subclass__(subclass) -> None:
        super().__init_subclass__()

        if not subclass.meta_.abstract:
            subclass.__validate_id_field()

        # Associate a `_projections` map with subclasses.
        #   It needs to be initialized here because if it
        #   were initialized in __init__, the same collection object
        #   would be made available across all subclasses,
        #   defeating its purpose.
        setattr(subclass, "_projections", defaultdict(set))

        # Store associated events
        setattr(subclass, "_events_cls_map", {})

    @classmethod
    def __validate_id_field(subclass):
        """Lookup the id field for this view and assign"""
        # FIXME What does it mean when there are no declared fields?
        #   Does it translate to an abstract view?
        if fields(subclass):
            try:
                id_field = next(
                    field
                    for _, field in fields(subclass).items()
                    if isinstance(field, (Field)) and field.identifier
                )

                setattr(subclass, _ID_FIELD_NAME, id_field.field_name)

            except StopIteration:
                raise IncorrectUsageError(
                    {
                        "_entity": [
                            f"Event Sourced Aggregate `{subclass.__name__}` needs to have at least one identifier"
                        ]
                    }
                )

    def __eq__(self, other):
        """Equivalence check to be based only on Identity"""

        # FIXME Enhanced Equality Checks
        #   * Ensure IDs have values and both of them are not null
        #   * Ensure that the ID is of the right type
        #   * Ensure that Objects belong to the same `type`
        #   * Check Reference equality

        # FIXME Check if `==` and `in` operator work with __eq__

        if type(other) is type(self):
            self_id = getattr(self, id_field(self).field_name)
            other_id = getattr(other, id_field(other).field_name)

            return self_id == other_id

        return False

    def __hash__(self):
        """Overrides the default implementation and bases hashing on identity"""

        # FIXME Add Object Class Type to hash
        return hash(getattr(self, id_field(self).field_name))

    def _apply(self, event_dict: Dict) -> None:
        """Apply the event onto the aggregate by calling the appropriate projection.

        Args:
            event (BaseEvent): Event object to apply
        """
        # FIXME Handle case of missing projection
        for fn in self._projections[event_dict["type"]]:
            event = self._events_cls_map[event_dict["type"]](
                **json.loads(event_dict["data"])
            )
            fn(self, event)


class apply:
    """Class decorator to mark methods in EventHandler classes."""

    def __init__(self, event_cls: "BaseEvent") -> None:
        self._event_cls = event_cls

    def __call__(self, fn: Callable) -> Callable:
        """Marks the method with a special `_event_cls` attribute to be able to
        construct a map of apply methods later.

        Args:
            fn (Callable): Event application method

        Returns:
            Callable: Handler method with `_event_cls` attribute
        """

        @functools.wraps(fn)
        def wrapper(instance, event_obj):
            fn(instance, event_obj)

        setattr(wrapper, "_event_cls", self._event_cls)
        return wrapper


def event_sourced_aggregate_factory(element_cls, **opts):
    element_cls = derive_element_class(element_cls, BaseEventSourcedAggregate, **opts)

    # Iterate through methods marked as `@apply` and construct a projections map
    methods = inspect.getmembers(element_cls, predicate=inspect.isroutine)
    for method_name, method in methods:
        if not (
            method_name.startswith("__") and method_name.endswith("__")
        ) and hasattr(method, "_event_cls"):
            element_cls._projections[fully_qualified_name(method._event_cls)].add(
                method
            )
            element_cls._events_cls_map[
                fully_qualified_name(method._event_cls)
            ] = method._event_cls

    return element_cls