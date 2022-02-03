from __future__ import annotations

import pytest

from protean import BaseEvent, BaseEventHandler, BaseEventSourcedAggregate, handle
from protean.fields import DateTime, Identifier, String


class User(BaseEventSourcedAggregate):
    id = Identifier(identifier=True)  # FIXME Auto-attach ID attribute
    email = String()
    name = String()
    password_hash = String()


class Email(BaseEventSourcedAggregate):
    id = Identifier(identifier=True)  # FIXME Auto-attach ID attribute
    email = String()
    sent_at = DateTime()


class Registered(BaseEvent):
    id = Identifier()
    email = String()
    name = String()
    password_hash = String()


class Activated(BaseEvent):
    id = Identifier()
    activated_at = DateTime()


class LoggedIn(BaseEvent):
    id = Identifier()
    activated_at = DateTime()

    class Meta:
        aggregate_cls = User


class Subscribed(BaseEvent):
    """An event generated by an external system in its own stream,
    that is consumed and stored as part of the User aggregate.
    """

    id = Identifier()

    class Meta:
        stream_name = "subscriptions"


class Sent(BaseEvent):
    email = String()
    sent_at = DateTime()


class Recalled(BaseEvent):
    email = String()
    sent_at = DateTime()

    class Meta:
        aggregate_cls = Email
        stream_name = "recalls"


class UserEventHandler(BaseEventHandler):
    @handle(Registered)
    def send_activation_email(self, _: Registered) -> None:
        pass

    @handle(Activated)
    def provision_user(self, _: Activated) -> None:
        pass

    @handle(Activated)
    def send_welcome_email(self, _: Activated) -> None:
        pass

    @handle(LoggedIn)
    def record_login(self, _: LoggedIn) -> None:
        pass

    @handle(Subscribed)
    def subscribed_for_notifications(self, _: Subscribed) -> None:
        pass


class EmailEventHandler(BaseEventHandler):
    @handle(Sent)
    def record_sent_email(self, _: Sent) -> None:
        pass

    @handle(Recalled)
    def record_recalls(self, _: Recalled) -> None:
        pass


@pytest.fixture(autouse=True)
def register(test_domain):
    test_domain.register(User)
    test_domain.register(Email)
    test_domain.register(UserEventHandler, aggregate_cls=User)
    test_domain.register(EmailEventHandler, aggregate_cls=Email)


def test_automatic_association_of_events_with_aggregate_and_stream():
    assert Registered.meta_.aggregate_cls is None
    assert Registered.meta_.stream_name == "user"

    assert Activated.meta_.aggregate_cls is None
    assert Activated.meta_.stream_name == "user"

    assert Subscribed.meta_.aggregate_cls == None
    assert Subscribed.meta_.stream_name == "subscriptions"

    assert Sent.meta_.aggregate_cls is None
    assert Sent.meta_.stream_name == "email"

    assert Recalled.meta_.aggregate_cls is Email
    assert Recalled.meta_.stream_name == "recalls"
