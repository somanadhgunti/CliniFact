"""PubMed E-utilities evidence retrieval without model or import-time side effects."""

from datetime import date
import re
from typing import Any, Protocol
from urllib.parse import quote
import xml.etree.ElementTree as ET

import httpx

from app.core.config import settings
from app.schemas.verification import EvidenceItem, EvidenceSource


PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


class PubMedServiceError(RuntimeError):
    """Base error for PubMed retrieval failures."""


class PubMedHTTPError(PubMedServiceError):
    """Raised when an E-utilities request fails."""


class PubMedResponseError(PubMedServiceError):
    """Raised when E-utilities returns an unusable response."""


class _HTTPClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any:
        ...


def _validate_claim(claim: str) -> str:
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be a non-empty string")
    claim = claim.strip()
    if len(claim) > settings.request_length_limit:
        raise ValueError(
            f"claim exceeds the {settings.request_length_limit}-character limit"
        )
    return claim


def _validate_limit(max_results: int, maximum: int) -> int:
    if (
        isinstance(max_results, bool)
        or not isinstance(max_results, int)
        or max_results < 1
        or max_results > maximum
    ):
        raise ValueError(
            f"max_results must be between 1 and {maximum}"
        )
    return max_results


def _date_from_article(article_date: ET.Element | None) -> date | None:
    if article_date is None:
        return None
    year = article_date.findtext("Year")
    month = article_date.findtext("Month") or "1"
    day = article_date.findtext("Day") or "1"
    if not year:
        return None
    month_number = int(month) if month.isdigit() else 1
    day_number = int(day) if day.isdigit() else 1
    try:
        return date(int(year), month_number, day_number)
    except ValueError:
        return None


def _abstract_text(article: ET.Element) -> str | None:
    parts = []
    for node in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
        text = "".join(node.itertext()).strip()
        if text:
            label = node.attrib.get("Label")
            parts.append(f"{label}: {text}" if label else text)
    return "\n\n".join(parts) or None


def _parse_fetch_xml(content: str) -> list[EvidenceItem]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise PubMedResponseError("PubMed metadata response was malformed XML") from error
    articles = root.findall(".//PubmedArticle")
    if not articles:
        raise PubMedResponseError(
            "PubMed metadata response contained no article records"
        )
    items = []
    for article in articles:
        pmid = article.findtext("./MedlineCitation/PMID")
        title = "".join(
            article.find("./MedlineCitation/Article/ArticleTitle").itertext()
        ) if article.find("./MedlineCitation/Article/ArticleTitle") is not None else ""
        if not pmid or not title.strip():
            raise PubMedResponseError("PubMed article metadata is missing PMID or title")
        items.append(
            EvidenceItem(
                source=EvidenceSource.PUBMED,
                title=title.strip(),
                abstract_or_excerpt=_abstract_text(article),
                publication_date=_date_from_article(
                    article.find(
                        "./MedlineCitation/Article/Journal/JournalIssue/PubDate"
                    )
                ),
                pmid=pmid.strip(),
                source_url=PUBMED_URL.format(pmid=quote(pmid.strip(), safe="")),
            )
        )
    return items


class PubMedService:
    def __init__(
        self,
        client: _HTTPClient | None = None,
        *,
        base_url: str = PUBMED_BASE_URL,
        timeout_seconds: float = settings.pubmed_timeout_seconds,
        api_key: str | None = settings.ncbi_api_key,
        email: str | None = settings.ncbi_email,
        max_results: int = settings.pubmed_max_results,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_results < 1 or max_results > 20:
            raise ValueError("max_results must be between 1 and 20")
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._email = email
        self._max_results = max_results

    def _params(self, **values: Any) -> dict[str, Any]:
        params = {"tool": "clinifact"}
        if self._email:
            params["email"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key
        params.update(values)
        return params

    def _get(self, endpoint: str, params: dict[str, Any]) -> Any:
        try:
            response = self._client.get(
                f"{self._base_url}/{endpoint}",
                params=params,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as error:
            raise PubMedHTTPError("PubMed request timed out") from error
        except httpx.HTTPError as error:
            raise PubMedHTTPError("PubMed request failed") from error

    def search(self, claim: str, max_results: int = 5) -> list[EvidenceItem]:
        claim = _validate_claim(claim)
        max_results = _validate_limit(max_results, self._max_results)
        search_response = self._get(
            "esearch.fcgi",
            self._params(db="pubmed", term=claim, retmax=max_results, retmode="json"),
        )
        try:
            payload = search_response.json()
            ids = payload["esearchresult"]["idlist"]
        except (ValueError, KeyError, TypeError) as error:
            raise PubMedResponseError("PubMed search response was malformed") from error
        if not isinstance(ids, list):
            raise PubMedResponseError("PubMed search ID list was malformed")
        ids = [str(identifier).strip() for identifier in ids if str(identifier).strip()]
        if not ids:
            return []
        fetch_response = self._get(
            "efetch.fcgi",
            self._params(db="pubmed", id=",".join(ids), retmode="xml"),
        )
        items = _parse_fetch_xml(fetch_response.text)
        by_pmid = {item.pmid: item for item in items}
        return [by_pmid[pmid] for pmid in ids if pmid in by_pmid]
