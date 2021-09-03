from datetime import datetime

from protean.core.aggregate import BaseAggregate
from protean.core.entity import BaseEntity
from protean.core.repository import BaseRepository
from protean.fields import DateTime, HasMany, HasOne, Integer, Reference, String, Text


class Post(BaseAggregate):
    title = String(required=True, max_length=1000)
    slug = String(required=True, max_length=1024)
    content = Text(required=True)
    posted_at = DateTime(required=True, default=datetime.now())

    meta = HasOne("tests.unit_of_work.aggregate_elements.PostMeta")
    comments = HasMany("tests.unit_of_work.aggregate_elements.Comment")


class PostMeta(BaseEntity):
    likes = Integer(default=0)

    post = Reference(Post)

    class Meta:
        aggregate_cls = Post


class Comment(BaseEntity):
    content = Text(required=True)
    commented_at = DateTime(required=True, default=datetime.now())

    post = Reference(Post)

    class Meta:
        aggregate_cls = Post


class PostRepository(BaseRepository):
    pass
