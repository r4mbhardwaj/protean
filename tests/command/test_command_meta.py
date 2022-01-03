from uuid import uuid4

import pytest

from protean import BaseCommand, BaseEventSourcedAggregate
from protean.exceptions import IncorrectUsageError
from protean.fields import String
from protean.fields.basic import Identifier


class User(BaseEventSourcedAggregate):
    id = Identifier(identifier=True)
    email = String()
    name = String()


class Register(BaseCommand):
    user_id = Identifier(identifier=True)
    email = String()
    name = String()


def test_command_definition_without_aggregate_or_stream(test_domain):
    test_domain.register(User)
    test_domain.register(Register)

    with pytest.raises(IncorrectUsageError) as exc:
        test_domain.process(
            Register(
                user_id=str(uuid4()),
                email="john.doe@gmail.com",
                name="John Doe",
            )
        )
    assert exc.value.messages == {
        "_entity": [
            f"Command `Register` needs to be associated with an aggregate or a stream"
        ]
    }


def test_command_associated_with_aggregate(test_domain):
    test_domain.register(User)
    test_domain.register(Register, aggregate_cls=User)

    identifier = str(uuid4())
    test_domain.process(
        Register(
            user_id=identifier,
            email="john.doe@gmail.com",
            name="John Doe",
        )
    )

    messages = test_domain.event_store.store.read("user:command")

    assert len(messages) == 1
    messages[0].stream_name == f"user:command-{identifier}"


def test_command_associated_with_stream_name(test_domain):
    test_domain.register(Register, stream_name="foo")

    identifier = str(uuid4())
    test_domain.process(
        Register(
            user_id=identifier,
            email="john.doe@gmail.com",
            name="John Doe",
        )
    )

    messages = test_domain.event_store.store.read("foo:command")

    assert len(messages) == 1
    messages[0].stream_name == f"foo:command-{identifier}"