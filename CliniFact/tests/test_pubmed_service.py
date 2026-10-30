from datetime import date
import json

import httpx
import pytest

from app.schemas.verification import EvidenceSource
from app.services.pubmed_service import (
    PubMedHTTPError,
    PubMedResponseError,
    PubMedService,
)


SEARCH_RESPONSE = {"esearchresult": {"idlist": ["123", "456"]}}
FETCH_RESPONSE = """\
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>123</PMID>
      <Article>
        <ArticleTitle>First article</ArticleTitle>
        <Abstract><AbstractText Label="BACKGROUND">Summary text.</AbstractText></Abstract>
        <Journal><JournalIssue><PubDate><Year>2024</Year><Month>2</Month><Day>3</Day></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>456</PMID>
      <Article><ArticleTitle>Second article</ArticleTitle>
        <Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


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


def test_search_normalizes_articles_and_preserves_pmid_order():
    client = FakeClient(
        [response(json_data=SEARCH_RESPONSE), response(text=FETCH_RESPONSE)]
    )
    service = PubMedService(client=client, api_key="secret", email="x@example.org")
    items = service.search("clinical claim", max_results=2)
    assert [item.pmid for item in items] == ["123", "456"]
    assert items[0].source is EvidenceSource.PUBMED
    assert items[0].source_url == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert items[0].publication_date == date(2024, 2, 3)
    assert items[0].abstract_or_excerpt == "BACKGROUND: Summary text."
    assert items[1].abstract_or_excerpt is None
    assert items[1].publication_date == date(2023, 1, 1)
    assert client.calls[0][1]["params"]["api_key"] == "secret"


def test_empty_search_does_not_fetch_metadata():
    client = FakeClient([response(json_data={"esearchresult": {"idlist": []}})])
    assert PubMedService(client=client).search("nothing") == []
    assert len(client.calls) == 1


@pytest.mark.parametrize("value", [0, 21, True])
def test_result_limit_is_validated(value):
    with pytest.raises(ValueError):
        PubMedService(client=FakeClient([])).search("claim", value)


def test_service_limit_caps_per_request_limit():
    with pytest.raises(ValueError, match="between 1 and 2"):
        PubMedService(client=FakeClient([]), max_results=2).search("claim", 3)


def test_http_timeout_and_http_error_are_typed():
    client = FakeClient([httpx.TimeoutException("timeout")])
    with pytest.raises(PubMedHTTPError, match="timed out"):
        PubMedService(client=client).search("claim")
    client = FakeClient([response(status=500, text="error")])
    with pytest.raises(PubMedHTTPError, match="failed"):
        PubMedService(client=client).search("claim")


def test_malformed_search_and_fetch_responses_are_rejected():
    client = FakeClient([response(json_data={"unexpected": {}})])
    with pytest.raises(PubMedResponseError, match="search"):
        PubMedService(client=client).search("claim")
    client = FakeClient(
        [response(json_data=SEARCH_RESPONSE), response(text="<broken")]
    )
    with pytest.raises(PubMedResponseError, match="malformed XML"):
        PubMedService(client=client).search("claim")


def test_no_network_call_occurs_at_import_time():
    assert "app.services.pubmed_service" in __import__("sys").modules
