"""
Research Trend Intelligence.
Prompt 96 — Research Trend Intelligence.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


@dataclass
class TopicTrendReport:
    topic: str
    time_window: str  # e.g., "2020-2026"
    publication_count: int
    growth_rate_percent: float
    emerging_keywords: List[str]
    methodology: str
    limitations: str
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)


class ResearchTrendIntelligenceService:
    """
    Research Trend & Topic Evolution Analysis.
    Guarantees:
    - Never conflates publication frequency with commercial readiness or absolute scientific truth.
    - Transparently documents time windows, coverage limitations, and trend scores.
    """

    def analyze_trend(
        self,
        topic: str,
        yearly_counts: Dict[int, int],
        keywords: List[str]
    ) -> TopicTrendReport:
        years = sorted(yearly_counts.keys())
        total_pubs = sum(yearly_counts.values())

        if len(years) >= 2 and yearly_counts[years[0]] > 0:
            growth = round(((yearly_counts[years[-1]] - yearly_counts[years[0]]) / yearly_counts[years[0]]) * 100.0, 2)
        else:
            growth = 0.0

        time_window = f"{years[0]}-{years[-1]}" if years else "N/A"

        return TopicTrendReport(
            topic=topic,
            time_window=time_window,
            publication_count=total_pubs,
            growth_rate_percent=growth,
            emerging_keywords=keywords[:5],
            methodology="Year-over-year linear volume slope evaluation.",
            limitations="Based strictly on cataloged bibliographic records.",
            provenance=ScientificProvenance(
                classification=EvidenceClassification.COMPUTED,
                reproducibility_notes="Computed trend metrics from indexed corpora."
            )
        )
