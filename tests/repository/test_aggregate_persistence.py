import pytest

from .elements import Person, PersonRepository


class TestAggregatePersistenceWithDictProvider:
    @pytest.fixture
    def test_domain(self):
        from protean.domain import Domain
        domain = Domain('Test', 'tests.repository.config')

        yield domain

    def test_retrieval_from_provider_connection(self, test_domain):
        conn = test_domain.providers.get_connection()
        assert conn is not None

        conn['data']['foo'] = 'bar'

        assert 'foo' in conn['data']
        assert conn['data']['foo'] == 'bar'


class TestAggregatePersistenceWithRepository:
    @pytest.fixture
    def test_domain(self):
        from protean.domain import Domain
        domain = Domain('Test', 'tests.repository.config')

        yield domain

    @pytest.fixture(autouse=True)
    def register_repositories(self, test_domain):
        test_domain.register(Person)
        test_domain.register(PersonRepository)
        yield

    @pytest.fixture
    def person_dao(self, test_domain):
        return test_domain.get_dao(Person)

    def test_new_object_persistence_with_no_uow(self, person_dao, test_domain):
        repo = test_domain.repository_for(Person)
        person = Person(first_name='John', last_name='Doe')
        repo.add(person)

        persisted_person = repo.get(person.id)
        assert persisted_person is not None

    def test_that_an_aggregate_object_can_be_persisted_via_dao(self, person_dao):
        person = Person(first_name='John', last_name='Doe', age=35)
        persisted_person = person_dao.save(person)

        assert persisted_person is not None
