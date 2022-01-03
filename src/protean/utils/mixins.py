from __future__ import annotations

import functools
import json

from collections import defaultdict
from enum import Enum
from typing import Callable, Dict, Union
from uuid import uuid4

from protean.container import BaseContainer, OptionsMixin
from protean.core.unit_of_work import UnitOfWork
from protean.core.value_object import BaseValueObject
from protean.exceptions import IncorrectUsageError
from protean.fields import Auto, DateTime, Dict, Integer, String, ValueObject
from protean.globals import current_domain
from protean.reflection import has_id_field, id_field
from protean.utils import fully_qualified_name


class handle:
    """Class decorator to mark handler methods in EventHandler and CommandHandler classes."""

    def __init__(self, target_cls: Union["BaseEvent", "BaseCommand"]) -> None:
        self._target_cls = target_cls

    def __call__(self, fn: Callable) -> Callable:
        """Marks the method with a special `_target_cls` attribute to be able to
        construct a map of handlers later.

        Args:
            fn (Callable): Handler method

        Returns:
            Callable: Handler method with `_target_cls` attribute
        """

        @functools.wraps(fn)
        def wrapper(instance, target_obj):
            # Wrap function call within a UoW
            with UnitOfWork():
                fn(instance, target_obj)

        setattr(wrapper, "_target_cls", self._target_cls)
        return wrapper


class HandlerMixin:
    """Mixin to add common handler behavior to Event Handlers and Command Handlers"""

    def __init_subclass__(subclass) -> None:
        super().__init_subclass__()

        # Associate a `_handlers` map with subclasses.
        #   It needs to be initialized here because if it
        #   were initialized in __init__, the same collection object
        #   would be made available across all subclasses,
        #   defeating its purpose.
        setattr(subclass, "_handlers", defaultdict(set))


class MessageType(Enum):
    EVENT = "EVENT"
    COMMAND = "COMMAND"


class MessageMetadata(BaseValueObject):
    kind = String(max_length=7, required=True, choices=MessageType)
    owner = String(max_length=50)
    schema_version = Integer()


class Message(BaseContainer, OptionsMixin):  # FIXME Remove OptionsMixin
    """Base class for Events and Commands.
    It provides concrete implementations for:
    - ID generation
    - Payload construction
    - Serialization and De-serialization
    """

    message_id = Auto(identifier=True)
    stream_name = String(max_length=255)
    type = String()
    data = Dict()
    expected_version = Integer()

    # Attributes filled when message is loaded from store
    time = DateTime()
    position = Integer()
    global_position = Integer()

    metadata = ValueObject(MessageMetadata)

    @classmethod
    def from_dict(cls, message: Dict) -> Message:
        return Message(
            stream_name=message["stream_name"],
            type=message["type"],
            data=json.loads(message["data"]),
            metadata=MessageMetadata(**json.loads(message["metadata"])),
            position=message["position"],
            global_position=message["global_position"],
            time=message["time"],
        )

    @classmethod
    def to_aggregate_event_message(
        cls, aggregate: "BaseEventSourcedAggregate", event: "BaseEvent"
    ) -> Message:
        identifier = getattr(aggregate, id_field(aggregate).field_name)

        return cls(
            stream_name=f"{aggregate.meta_.stream_name}-{identifier}",
            type=fully_qualified_name(event.__class__),
            data=event.to_dict(),
            metadata=MessageMetadata(
                kind=MessageType.EVENT.value,
                owner=current_domain.domain_name,
                # schema_version=event.meta_.version,  # FIXME Maintain version for event
            )
            # expected_version=aggregate.version  # FIXME Maintain version for Aggregates
        )

    def to_object(self) -> Union["BaseEvent", "BaseCommand"]:
        if self.metadata.kind == MessageType.EVENT.value:
            element_record = current_domain.registry.events[self.type]
        elif self.metadata.kind == MessageType.COMMAND.value:
            element_record = current_domain.registry.commands[self.type]
        else:
            raise NotImplementedError  # FIXME Handle unknown messages better

        return element_record.cls(**self.data)

    @classmethod
    def to_event_message(cls, event: "BaseEvent"):
        # FIXME Should one of `aggregate_cls` or `stream_name` be mandatory?
        if not (event.meta_.aggregate_cls or event.meta_.stream_name):
            raise IncorrectUsageError(
                {
                    "_entity": [
                        f"Event `{event.__class__.__name__}` needs to be associated with an aggregate or a stream"
                    ]
                }
            )

        if has_id_field(event):
            identifier = getattr(event, id_field(event).field_name)
        else:
            identifier = str(uuid4())

        # Use explicit stream name if provided, or fallback on Aggregate's stream name
        stream_name = (
            event.meta_.stream_name or event.meta_.aggregate_cls.meta_.stream_name
        )

        return cls(
            stream_name=f"{stream_name}-{identifier}",
            type=fully_qualified_name(event.__class__),
            data=event.to_dict(),
            metadata=MessageMetadata(
                kind=MessageType.EVENT.value,
                owner=current_domain.domain_name,
            )
            # schema_version=command.meta_.version,  # FIXME Maintain version for event
        )

    @classmethod
    def to_command_message(cls, command: "BaseCommand") -> Message:
        # FIXME Should one of `aggregate_cls` or `stream_name` be mandatory?
        if not (command.meta_.aggregate_cls or command.meta_.stream_name):
            raise IncorrectUsageError(
                {
                    "_entity": [
                        f"Command `{command.__class__.__name__}` needs to be associated with an aggregate or a stream"
                    ]
                }
            )

        # Use the value of an identifier field if specified, or generate a new uuid
        if has_id_field(command):
            identifier = getattr(command, id_field(command).field_name)
        else:
            identifier = str(uuid4())

        # Use explicit stream name if provided, or fallback on Aggregate's stream name
        stream_name = (
            command.meta_.stream_name or command.meta_.aggregate_cls.meta_.stream_name
        )

        return cls(
            stream_name=f"{stream_name}:command-{identifier}",
            type=fully_qualified_name(command.__class__),
            data=command.to_dict(),
            metadata=MessageMetadata(
                kind=MessageType.COMMAND.value,
                owner=current_domain.domain_name,
            )
            # schema_version=command.meta_.version,  # FIXME Maintain version for command
        )