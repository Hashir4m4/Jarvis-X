"""
Patent Intelligence & Landscape Analysis.
Prompt 98 — Patent Intelligence.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


@dataclass
class PatentRecord:
    patent_number: str
    title: str
    assignee: str
    filing_date: str
    publication_date: str
    abstract: str
    claims: List[str]
    classification_codes: List[str]  # e.g., IPC/CPC codes: H01L, C01B
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patent_number": self.patent_number,
            "title": self.title,
            "assignee": self.assignee,
            "filing_date": self.filing_date,
            "publication_date": self.publication_date,
            "abstract": self.abstract,
            "claims": self.claims,
            "classification_codes": self.classification_codes,
            "provenance": self.provenance.to_dict()
        }


class PatentIntelligenceService:
    """
    Patent Prior-Art & Landscape Intelligence.
    Guarantees:
    - Provides research assistance only, NOT legal clearance or formal FTO opinions.
    - Discloses search scope and attributes claims strictly to official published filings.
    """

    def __init__(self):
        self._patents: Dict[str, PatentRecord] = {}

    def index_patent(
        self,
        patent_number: str,
        title: str,
        assignee: str,
        filing_date: str,
        publication_date: str,
        abstract: str,
        claims: List[str],
        classification_codes: List[str]
    ) -> PatentRecord:
        rec = PatentRecord(
            patent_number=patent_number,
            title=title,
            assignee=assignee,
            filing_date=filing_date,
            publication_date=publication_date,
            abstract=abstract,
            claims=claims,
            classification_codes=classification_codes,
            provenance=ScientificProvenance(
                source_identifier=patent_number,
                classification=EvidenceClassification.PUBLISHED,
                reproducibility_notes="Patent bibliographic & claim data from official gazette/office."
            )
        )
        self._patents[patent_number] = rec
        return rec

    def search_prior_art(self, keyword: str) -> List[Dict[str, Any]]:
        k = keyword.lower()
        results = []
        for p in self._patents.values():
            if k in p.title.lower() or k in p.abstract.lower() or any(k in c.lower() for c in p.claims):
                results.append(p.to_dict())
        return results

    def get_patent(self, patent_number: str) -> Optional[PatentRecord]:
        return self._patents.get(patent_number)
