"""Module with repository implementation for SQLAlchemy"""
import logging
import uuid

from abc import ABCMeta
from typing import Any

import sqlalchemy.dialects.postgresql as psql

from sqlalchemy import Column, MetaData, and_, create_engine, or_, orm
from sqlalchemy import types as sa_types
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext import declarative as sa_dec
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.types import CHAR, TypeDecorator

from protean.core.model import BaseModel
from protean.exceptions import ConfigurationError, ObjectNotFoundError
from protean.fields import (
    Auto,
    Boolean,
    Date,
    DateTime,
    Dict,
    Float,
    Identifier,
    Integer,
    List,
    String,
    Text,
)
from protean.fields.association import Reference, _ReferenceField
from protean.fields.embedded import _ShadowField
from protean.globals import current_domain, current_uow
from protean.port.dao import BaseDAO, BaseLookup, ResultSet
from protean.port.provider import BaseProvider
from protean.reflection import attributes, id_field
from protean.utils import Database, IdentityType
from protean.utils.query import Q

logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logger = logging.getLogger("protean.repository")


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(psql.UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


def _get_identity_type():
    """Retrieve the configured data type for AutoGenerated Identifiers

    If `current_domain` is not yet available, it simply means that Protean is still being loaded.
    Default to `Identity.STRING`
    """
    try:
        if current_domain.config["IDENTITY_TYPE"] == IdentityType.INTEGER.value:
            return sa_types.Integer
        elif current_domain.config["IDENTITY_TYPE"] == IdentityType.STRING.value:
            return sa_types.String
        elif current_domain.config["IDENTITY_TYPE"] == IdentityType.UUID.value:
            return GUID
        else:
            raise ConfigurationError(
                f'Unknown Identity Type {current_domain.config["IDENTITY_TYPE"]}'
            )
    except RuntimeError as exc:
        logger.error(f"RuntimeError while identifying data type for identities: {exc}")
        return sa_types.String


class DeclarativeMeta(sa_dec.DeclarativeMeta, ABCMeta):
    """ Metaclass for the Sqlalchemy declarative schema """

    def __init__(cls, classname, bases, dict_):  # noqa: C901
        # Update the class attrs with the entity attributes

        field_mapping = {
            Auto: _get_identity_type(),
            Boolean: sa_types.Boolean,
            Date: sa_types.Date,
            DateTime: sa_types.DateTime,
            Dict: sa_types.PickleType,
            Float: sa_types.Float,
            Identifier: _get_identity_type(),
            Integer: sa_types.Integer,
            List: sa_types.PickleType,
            String: sa_types.String,
            Text: sa_types.Text,
            _ReferenceField: _get_identity_type(),
        }

        if "meta_" in dict_:
            entity_cls = dict_["meta_"].entity_cls
            for _, field_obj in attributes(entity_cls).items():
                attribute_name = field_obj.attribute_name

                # Map the field if not in attributes
                if attribute_name not in cls.__dict__:
                    # Derive field based on field enclosed within ShadowField
                    if isinstance(field_obj, _ShadowField):
                        field_obj = field_obj.field_obj

                    field_cls = type(field_obj)
                    type_args = []
                    type_kwargs = {}

                    # Get the SA type
                    sa_type_cls = field_mapping.get(field_cls)

                    # Upgrade to Postgresql specific Data Types
                    if cls.metadata.bind.dialect.name == "postgresql":

                        if field_cls == Dict and not field_obj.pickled:
                            sa_type_cls = psql.JSON

                        if field_cls == List and not field_obj.pickled:
                            sa_type_cls = psql.ARRAY

                            # Associate Content Type
                            if field_obj.content_type:
                                type_args.append(
                                    field_mapping.get(field_obj.content_type)
                                )
                            else:
                                type_args.append(sa_types.Text)

                    # Default to the text type if no mapping is found
                    if not sa_type_cls:
                        sa_type_cls = sa_types.String

                    # Build the column arguments
                    col_args = {
                        "primary_key": field_obj.identifier,
                        "nullable": not field_obj.required,
                        "unique": field_obj.unique,
                    }

                    # Update the arguments based on the field type
                    if issubclass(field_cls, String):
                        type_kwargs["length"] = field_obj.max_length

                    # Update the attributes of the class
                    dict_[attribute_name] = Column(
                        sa_type_cls(*type_args, **type_kwargs), **col_args
                    )
        super().__init__(classname, bases, dict_)


def derive_schema_name(model_cls):
    if hasattr(model_cls.meta_, "schema_name"):
        return model_cls.meta_.schema_name
    else:
        return model_cls.meta_.entity_cls.meta_.schema_name


@as_declarative(metaclass=DeclarativeMeta)
class SqlalchemyModel(BaseModel):
    """Model representation for the Sqlalchemy Database """

    @declared_attr
    def __tablename__(cls):
        return derive_schema_name(cls)

    @classmethod
    def from_entity(cls, entity):
        """ Convert the entity to a model object """
        item_dict = {}
        for attribute_obj in attributes(cls.meta_.entity_cls).values():
            if isinstance(attribute_obj, Reference):
                item_dict[
                    attribute_obj.relation.attribute_name
                ] = attribute_obj.relation.value
            else:
                item_dict[attribute_obj.attribute_name] = getattr(
                    entity, attribute_obj.attribute_name
                )
        return cls(**item_dict)

    @classmethod
    def to_entity(cls, model_obj: "SqlalchemyModel"):
        """ Convert the model object to an entity """
        item_dict = {}
        for field_name in attributes(cls.meta_.entity_cls):
            item_dict[field_name] = getattr(model_obj, field_name, None)
        return cls.meta_.entity_cls(item_dict)


class SADAO(BaseDAO):
    """DAO implementation for Databases compliant with SQLAlchemy"""

    def __repr__(self) -> str:
        return f"SQLAlchemyDAO <{self.entity_cls.__name__}>"

    def _get_session(self):
        """Returns an active connection to the persistence store.

        - If there is an active transaction, the connection associated with the transaction (in the UoW) is returned
        - If the DAO has been explicitly instructed to work outside a UoW (with the help of `_outside_uow`), or if
            there are no active transactions, a new connection is retrieved from the provider and returned.

        Overridden here instead of using the version in `BaseDAO` because the connection needs to be started
            with a call to `begin()` if it is not yet active (checked with `is_active`)
        """
        if current_uow and not self._outside_uow:
            return current_uow.get_session(self.provider.name)
        else:
            new_connection = self.provider.get_connection()
            if not new_connection.is_active:
                new_connection.begin()
            return new_connection

    def _build_filters(self, criteria: Q):
        """ Recursively Build the filters from the criteria object"""
        # Decide the function based on the connector type
        func = and_ if criteria.connector == criteria.AND else or_
        params = []
        for child in criteria.children:
            if isinstance(child, Q):
                # Call the function again with the child
                params.append(self._build_filters(child))
            else:
                # Find the lookup class and the key
                stripped_key, lookup_class = self.provider._extract_lookup(child[0])

                # Instantiate the lookup class and get the expression
                lookup = lookup_class(stripped_key, child[1], self.model_cls)
                if criteria.negated:
                    params.append(~lookup.as_expression())
                else:
                    params.append(lookup.as_expression())

        return func(*params)

    def _filter(
        self, criteria: Q, offset: int = 0, limit: int = 10, order_by: list = ()
    ) -> ResultSet:
        """ Filter objects from the sqlalchemy database """
        conn = self._get_session()
        qs = conn.query(self.model_cls)

        # Build the filters from the criteria
        if criteria.children:
            qs = qs.filter(self._build_filters(criteria))

        # Apply the order by clause if present
        order_cols = []
        for order_col in order_by:
            col = getattr(self.model_cls, order_col.lstrip("-"))
            if order_col.startswith("-"):
                order_cols.append(col.desc())
            else:
                order_cols.append(col)
        qs = qs.order_by(*order_cols)
        qs_without_limit = qs
        qs = qs.limit(limit).offset(offset)

        # Return the results
        try:
            items = qs.all()
            result = ResultSet(
                offset=offset, limit=limit, total=qs_without_limit.count(), items=items
            )
        except DatabaseError as exc:
            logger.error(f"Error while filtering: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return result

    def _create(self, model_obj):
        """ Add a new record to the sqlalchemy database"""
        conn = self._get_session()

        try:
            conn.add(model_obj)
        except DatabaseError as exc:
            logger.error(f"Error while creating: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return model_obj

    def _update(self, model_obj):
        """ Update a record in the sqlalchemy database"""
        conn = self._get_session()
        db_item = None

        # Fetch the record from database
        try:
            identifier = getattr(model_obj, id_field(self.entity_cls).attribute_name)
            db_item = conn.query(self.model_cls).get(
                identifier
            )  # This will raise exception if object was not found
        except DatabaseError as exc:
            logger.error(f"Database Record not found: {exc}")
            raise

        if db_item is None:
            conn.rollback()
            conn.close()
            raise ObjectNotFoundError(
                {
                    "_entity": f"`{self.entity_cls.__name__}` object with identifier {identifier} "
                    f"does not exist."
                }
            )

        # Sync DB Record with current changes. When the session is committed, changes are automatically synced
        try:
            for attribute in attributes(self.entity_cls):
                if attribute != id_field(self.entity_cls).attribute_name and getattr(
                    model_obj, attribute
                ) != getattr(db_item, attribute):
                    setattr(db_item, attribute, getattr(model_obj, attribute))
        except DatabaseError as exc:
            logger.error(f"Error while updating: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return model_obj

    def _update_all(self, criteria: Q, *args, **kwargs):
        """ Update all objects satisfying the criteria """
        conn = self._get_session()
        qs = conn.query(self.model_cls).filter(self._build_filters(criteria))
        try:
            values = {}
            if args:
                values = args[
                    0
                ]  # `args[0]` is required because `*args` is sent as a tuple
            values.update(kwargs)
            updated_count = qs.update(values)
        except DatabaseError as exc:
            logger.error(f"Error while updating all: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return updated_count

    def _delete(self, model_obj):
        """ Delete the entity record in the dictionary """
        conn = self._get_session()
        db_item = None

        # Fetch the record from database
        try:
            identifier = getattr(model_obj, id_field(self.entity_cls).attribute_name)
            db_item = conn.query(self.model_cls).get(
                identifier
            )  # This will raise exception if object was not found
        except DatabaseError as exc:
            logger.error(f"Database Record not found: {exc}")
            raise

        if db_item is None:
            conn.rollback()
            conn.close()
            raise ObjectNotFoundError(
                {
                    "_entity": f"`{self.entity_cls.__name__}` object with identifier {identifier} "
                    f"does not exist."
                }
            )

        try:
            conn.delete(db_item)
        except DatabaseError as exc:
            logger.error(f"Error while deleting: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return model_obj

    def _delete_all(self, criteria: Q = None):
        """ Delete a record from the sqlalchemy database"""
        conn = self._get_session()

        del_count = 0
        if criteria:
            qs = conn.query(self.model_cls).filter(self._build_filters(criteria))
        else:
            qs = conn.query(self.model_cls)

        try:
            del_count = qs.delete()
        except DatabaseError as exc:
            logger.error(f"Error while deleting all: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return del_count

    def _raw(self, query: Any, data: Any = None):
        """Run a raw query on the repository and return entity objects"""
        assert isinstance(query, str)

        conn = self._get_session()
        try:
            results = conn.execute(query)

            entity_items = []
            for item in results:
                entity = self.model_cls.to_entity(item)
                entity.state_.mark_retrieved()
                entity_items.append(entity)

            result = ResultSet(
                offset=0,
                limit=len(entity_items),
                total=len(entity_items),
                items=entity_items,
            )
        except DatabaseError as exc:
            logger.error(f"Error while running raw query: {exc}")
            raise
        finally:
            if not current_uow:
                conn.commit()
                conn.close()

        return result


class SAProvider(BaseProvider):
    """Provider Implementation class for SQLAlchemy"""

    def __init__(self, *args, **kwargs):
        """Initialize and maintain Engine"""
        # Since SQLAlchemyProvider can cater to multiple databases, it is important
        #   that we know which database we are dealing with, to run database-specific
        #   statements like `PRAGMA` for SQLite.
        if "DATABASE" not in args[2]:
            logger.error(f"Missing `DATABASE` information in conn_info: {args[2]}")
            raise ConfigurationError("Missing `DATABASE` attribute in Connection info")

        super().__init__(*args, **kwargs)

        kwargs = self._get_database_specific_engine_args()

        self._engine = create_engine(make_url(self.conn_info["DATABASE_URI"]), **kwargs)

        if self.conn_info["DATABASE"] == Database.POSTGRESQL.value:
            # Nest database tables under a schema, so that we have complete control
            #   on creating/dropping db structures. We cannot control structures in the
            #   the default `public` schema.
            #
            # Use `SCHEMA` value if specified as part of the conn info. Otherwise, construct
            #   and use default schema name as `DB`_schema.
            schema = (
                self.conn_info["SCHEMA"] if "SCHEMA" in self.conn_info else "public"
            )

            self._metadata = MetaData(bind=self._engine, schema=schema)
        else:
            self._metadata = MetaData(bind=self._engine)

        # A temporary cache of already constructed model classes
        self._model_classes = {}

    def _get_database_specific_engine_args(self):
        """ Supplies additional database-specific arguments to SQLAlchemy Engine.

        Return: a dictionary with database-specific SQLAlchemy Engine arguments.
        """
        if self.conn_info["DATABASE"] == Database.POSTGRESQL.value:
            return {"isolation_level": "AUTOCOMMIT"}

        return {}

    def _get_database_specific_session_args(self):
        """ Set Database specific session parameters.

        Depending on the database in use, this method supplies
        additional arguments while constructing sessions.

        Return: a dictionary with additional arguments and values.
        """
        if self.conn_info["DATABASE"] == Database.POSTGRESQL.value:
            return {"autocommit": True, "autoflush": False}

        return {}

    def get_session(self):
        """Establish a session to the Database"""
        # Create the session
        kwargs = self._get_database_specific_session_args()
        session_factory = orm.sessionmaker(
            bind=self._engine, expire_on_commit=False, **kwargs
        )
        session_cls = orm.scoped_session(session_factory)

        return session_cls

    def _execute_database_specific_connection_statements(self, conn):
        """ Execute connection statements depending on the database in use.

        Each database has a unique set of commands and associated format to control
        connection-related parameters. Since we use SQLAlchemy, statements should
        be run dynamically based on the database in use.

        Arguments:
        * conn: An active connection object to the database

        Return: None
        """
        if self.conn_info["DATABASE"] == Database.SQLITE.value:
            conn.execute("PRAGMA case_sensitive_like = ON;")

        return conn

    def get_connection(self, session_cls=None):
        """ Create the connection to the Database instance"""
        # If this connection has to be created within an existing session,
        #   ``session_cls`` will be provided as an argument.
        #   Otherwise, fetch a new ``session_cls`` from ``get_session()``
        if session_cls is None:
            session_cls = self.get_session()

        conn = session_cls()
        conn = self._execute_database_specific_connection_statements(conn)

        return conn

    def _data_reset(self):
        conn = self._engine.connect()

        transaction = conn.begin()

        if self.conn_info["DATABASE"] == Database.SQLITE.value:
            conn.execute("PRAGMA foreign_keys = OFF;")

        for table in self._metadata.sorted_tables:
            conn.execute(table.delete())

        if self.conn_info["DATABASE"] == Database.SQLITE.value:
            conn.execute("PRAGMA foreign_keys = ON;")

        transaction.commit()

        # Discard any active Unit of Work
        if current_uow and current_uow.in_progress:
            current_uow.rollback()

    def _create_database_artifacts(self):
        for _, aggregate_record in self.domain.registry.aggregates.items():
            self.domain.repository_for(aggregate_record.cls)._dao

        self._metadata.create_all()

    def _drop_database_artifacts(self):
        self._metadata.drop_all()

    def decorate_model_class(self, entity_cls, model_cls):
        schema_name = derive_schema_name(model_cls)

        # Return the model class if it was already seen/decorated
        if schema_name in self._model_classes:
            return self._model_classes[schema_name]

        # If `model_cls` is already subclassed from SqlAlchemyModel,
        #   this method call is a no-op
        if issubclass(model_cls, SqlalchemyModel):
            return model_cls
        else:
            custom_attrs = {
                key: value
                for (key, value) in vars(model_cls).items()
                if key not in ["Meta", "__module__", "__doc__", "__weakref__"]
            }

            from protean.core.model import ModelMeta

            meta_ = ModelMeta()
            meta_.entity_cls = entity_cls

            custom_attrs.update({"meta_": meta_, "metadata": self._metadata})
            # FIXME Ensure the custom model attributes are constructed properly
            decorated_model_cls = type(
                model_cls.__name__, (SqlalchemyModel, model_cls), custom_attrs
            )

            # Memoize the constructed model class
            self._model_classes[schema_name] = decorated_model_cls

            return decorated_model_cls

    def construct_model_class(self, entity_cls):
        """Return a fully-baked Model class for a given Entity class"""
        model_cls = None

        # Return the model class if it was already seen/decorated
        if entity_cls.meta_.schema_name in self._model_classes:
            model_cls = self._model_classes[entity_cls.meta_.schema_name]
        else:
            from protean.core.model import ModelMeta

            meta_ = ModelMeta()
            meta_.entity_cls = entity_cls

            attrs = {
                "meta_": meta_,
                "metadata": self._metadata,
            }
            # FIXME Ensure the custom model attributes are constructed properly
            model_cls = type(entity_cls.__name__ + "Model", (SqlalchemyModel,), attrs)

            # Memoize the constructed model class
            self._model_classes[entity_cls.meta_.schema_name] = model_cls

        # Set Entity Class as a class level attribute for the Model, to be able to reference later.
        return model_cls

    def get_dao(self, entity_cls, model_cls):
        """ Return a DAO object configured with a live connection"""
        return SADAO(self.domain, self, entity_cls, model_cls)

    def raw(self, query: Any, data: Any = None):
        """Run raw query on Provider"""
        if data is None:
            data = {}
        assert isinstance(query, str)
        assert isinstance(data, (dict, None))

        return self.get_connection().execute(query, data)


operators = {
    "exact": "__eq__",
    "iexact": "ilike",
    "contains": "contains",
    "icontains": "ilike",
    "startswith": "startswith",
    "endswith": "endswith",
    "gt": "__gt__",
    "gte": "__ge__",
    "lt": "__lt__",
    "lte": "__le__",
    "in": "in_",
    "any": "any",
    "overlap": "overlap",
}


class DefaultLookup(BaseLookup):
    """Base class with default implementation of expression construction"""

    def __init__(self, source, target, model_cls):
        """Source is LHS and Target is RHS of a comparsion"""
        self.model_cls = model_cls
        super().__init__(source, target)

    def process_source(self):
        """Return source with transformations, if any"""
        source_col = getattr(self.model_cls, self.source)
        return source_col

    def process_target(self):
        """Return target with transformations, if any"""
        return self.target

    def as_expression(self):
        lookup_func = getattr(self.process_source(), operators[self.lookup_name])
        return lookup_func(self.process_target())


@SAProvider.register_lookup
class Exact(DefaultLookup):
    """Exact Match Query"""

    lookup_name = "exact"


@SAProvider.register_lookup
class IExact(DefaultLookup):
    """Exact Case-Insensitive Match Query"""

    lookup_name = "iexact"


@SAProvider.register_lookup
class Contains(DefaultLookup):
    """Exact Contains Query"""

    lookup_name = "contains"


@SAProvider.register_lookup
class IContains(DefaultLookup):
    """Case-Insensitive Contains Query"""

    lookup_name = "icontains"

    def process_target(self):
        """Return target in lowercase"""
        assert isinstance(self.target, str)
        return f"%{super().process_target()}%"


@SAProvider.register_lookup
class Startswith(DefaultLookup):
    """Exact Contains Query"""

    lookup_name = "startswith"


@SAProvider.register_lookup
class Endswith(DefaultLookup):
    """Exact Contains Query"""

    lookup_name = "endswith"


@SAProvider.register_lookup
class GreaterThan(DefaultLookup):
    """Greater than Query"""

    lookup_name = "gt"


@SAProvider.register_lookup
class GreaterThanOrEqual(DefaultLookup):
    """Greater than or Equal Query"""

    lookup_name = "gte"


@SAProvider.register_lookup
class LessThan(DefaultLookup):
    """Less than Query"""

    lookup_name = "lt"


@SAProvider.register_lookup
class LessThanOrEqual(DefaultLookup):
    """Less than or Equal Query"""

    lookup_name = "lte"


@SAProvider.register_lookup
class In(DefaultLookup):
    """In Query"""

    lookup_name = "in"

    def process_target(self):
        """Ensure target is a list or tuple"""
        assert isinstance(self.target, (list, tuple))
        return super().process_target()


@SAProvider.register_lookup
class Any(DefaultLookup):
    """Any Query"""

    lookup_name = "any"


@SAProvider.register_lookup
class Overlap(DefaultLookup):
    """Overlap Query"""

    lookup_name = "overlap"
