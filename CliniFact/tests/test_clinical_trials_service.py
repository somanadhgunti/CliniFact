from datetime import date

import httpx
import pytest

from app.schemas.verification import EvidenceSource
from app.services.clinical_trials_service import (
    ClinicalTrialsHTTPError,
    ClinicalTrialsResponseError,
    ClinicalTrialsService,
)


STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT01234567",
            "briefTitle": "A study of an intervention",
            "officialTitle": "Official study title",
        },
        "descriptionModule": {"briefSummary": "A brief trial summary."},
        "statusModule": {
            "overallStatus": "COMPLETED",
            "startDateStruct": {"date": "2021-02"},
            "completionDateStruct": {"date": "2023-04-15"},
        },
    }
}


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(status=200, *, json_data=None, text=""):
    return httpx.Response(
        status,
        json=json_data,
        text=text if json_data is None else None,
        request=httpx.Request("GET", "https://example.test"),
    )


def test_search_normalizes_trial_and_request_parameters():
    client = FakeClient([response(json_data={"studies": [STUDY]})])
    item = ClinicalTrialsService(client=client).search("clinical claim", 1)[0]
    assert item.source is EvidenceSource.CLINICALTRIALS_GOV
    assert item.nct_id == "NCT01234567"
    assert item.source_url == "https://clinicaltrials.gov/study/NCT01234567"
    assert item.study_status == "COMPLETED"
    assert item.start_date == date(2021, 2, 1)
    assert item.completion_date == date(2023, 4, 15)
    assert item.abstract_or_excerpt == "A brief trial summary."
    assert client.calls[0][1]["params"] == {
        "query.term": "clinical claim",
        "pageSize": 1,
    }


def test_missing_optional_fields_are_none_and_invalid_studies_are_skipped():
    missing = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT99999999", "briefTitle": "Minimal"}
        }
    }
    client = FakeClient([response(json_data={"studies": [missing, {"bad": "study"}]})])
    items = ClinicalTrialsService(client=client).search("claim")
    assert len(items) == 1
    assert items[0].study_status is None
    assert items[0].start_date is None
    assert items[0].completion_date is None
    assert items[0].abstract_or_excerpt is None


def test_empty_results_return_empty_list():
    client = FakeClient([response(json_data={"studies": []})])
    assert ClinicalTrialsService(client=client).search("nothing") == []


@pytest.mark.parametrize("value", [0, 21, True])
def test_result_limit_is_validated(value):
    with pytest.raises(ValueError):
        ClinicalTrialsService(client=FakeClient([])).search("claim", value)


def test_http_timeout_and_http_error_are_typed():
    client = FakeClient([httpx.TimeoutException("timeout")])
    with pytest.raises(ClinicalTrialsHTTPError, match="timed out"):
        ClinicalTrialsService(client=client).search("claim")
    client = FakeClient([response(status=500, text="error")])
    with pytest.raises(ClinicalTrialsHTTPError, match="failed"):
        ClinicalTrialsService(client=client).search("claim")


def test_malformed_api_responses_are_rejected():
    client = FakeClient([response(json_data={"unexpected": []})])
    with pytest.raises(ClinicalTrialsResponseError, match="missing studies"):
        ClinicalTrialsService(client=client).search("claim")
    client = FakeClient([response(json_data={"studies": {}})])
    with pytest.raises(ClinicalTrialsResponseError, match="studies field"):
        ClinicalTrialsService(client=client).search("claim")
    client = FakeClient([response(status=200, text="not-json")])
    with pytest.raises(ClinicalTrialsResponseError, match="valid JSON"):
        ClinicalTrialsService(client=client).search("claim")


def test_no_network_call_occurs_during_module_import():
    assert "app.services.clinical_trials_service" in __import__("sys").modules
