import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from batchbuilder.apollo import RecordedApolloClient  # noqa: E402
from batchbuilder.models import PbiSample, QcRecord  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXPECTED = FIXTURES / "expected"
SAMPLE_XLS = FIXTURES / "tox4_sample_plate.xls"


@pytest.fixture(scope="session")
def fixture_data():
    return json.loads((FIXTURES / "apollo_fixture.json").read_text())


@pytest.fixture(scope="session")
def apollo(fixture_data):
    """Apollo results recorded from the batch the shipped sample files came from."""
    return RecordedApolloClient(
        valid_mbns=fixture_data["valid_mbns"],
        pbi=[PbiSample(*row) for row in fixture_data["pbi"]],
        qc={mbn: [QcRecord(*row) for row in rows]
            for mbn, rows in fixture_data["qc_data"].items()},
    )


@pytest.fixture(scope="session")
def batch_params(fixture_data):
    return fixture_data["batch"]
