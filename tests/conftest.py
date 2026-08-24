"Shared fixtures. Every test gets its own vault, and no test loads a model."
import pytest

from pobblebonk.core import vault
from pobblebonk.pob import Pob
from pobblebonk.run import FakeRunner


@pytest.fixture
def db():
    "An in-memory vault."
    return vault()


@pytest.fixture
def pob(db):
    "Everything on one in-memory vault, with a runner that answers `ok`."
    return Pob(db=db).attach(FakeRunner())


@pytest.fixture
def filedb(tmp_path):
    "A vault on disk, for the tests that need more than one process on it."
    return str(tmp_path/'vault.db')
