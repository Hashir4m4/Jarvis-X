"""
Scientific Data Analysis & Statistics Engine.
Prompt 92 — Scientific Data Analysis.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


@dataclass
class DatasetQualityReport:
    total_rows: int
    column_types: Dict[str, str]
    missing_value_counts: Dict[str, int]
    outliers_detected: Dict[str, int]
    is_valid: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class ColumnStatistics:
    column_name: str
    count: int
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    median: float


class ScientificDataAnalysisService:
    """
    Scientific Data Analysis & Statistical Quality Validation.
    Guarantees:
    - Never modifies raw input records in place.
    - Preserves measurement units and reports missingness / outliers explicitly.
    """

    def validate_dataset(self, data: List[Dict[str, Any]]) -> DatasetQualityReport:
        if not data:
            return DatasetQualityReport(
                total_rows=0,
                column_types={},
                missing_value_counts={},
                outliers_detected={},
                is_valid=False,
                warnings=["Empty dataset provided."]
            )

        total_rows = len(data)
        cols = list(data[0].keys())
        missing_counts: Dict[str, int] = {c: 0 for c in cols}
        types: Dict[str, str] = {}
        outliers: Dict[str, int] = {c: 0 for c in cols}
        warnings: List[str] = []

        # Analyze columns
        for c in cols:
            values = [row.get(c) for row in data]
            none_count = sum(1 for v in values if v is None or v == "")
            missing_counts[c] = none_count
            if none_count > 0:
                warnings.append(f"Column '{c}' contains {none_count} missing values.")

            num_vals = [v for v in values if isinstance(v, (int, float))]
            if len(num_vals) == len(values) - none_count and num_vals:
                types[c] = "numeric"
                # 3-sigma outlier detection
                mean_val = sum(num_vals) / len(num_vals)
                variance = sum((x - mean_val) ** 2 for x in num_vals) / len(num_vals)
                std = math.sqrt(variance)
                if std > 0:
                    outlier_count = sum(1 for x in num_vals if abs(x - mean_val) > 3 * std)
                    outliers[c] = outlier_count
                    if outlier_count > 0:
                        warnings.append(f"Column '{c}' contains {outlier_count} statistical 3-sigma outliers.")
            else:
                types[c] = "categorical"

        return DatasetQualityReport(
            total_rows=total_rows,
            column_types=types,
            missing_value_counts=missing_counts,
            outliers_detected=outliers,
            is_valid=True,
            warnings=warnings
        )

    def calculate_descriptive_stats(self, values: List[float], column_name: str = "metric") -> Optional[ColumnStatistics]:
        clean = [v for v in values if v is not None and not math.isnan(v)]
        if not clean:
            return None

        n = len(clean)
        mean_val = sum(clean) / n
        var = sum((x - mean_val) ** 2 for x in clean) / n
        std = math.sqrt(var)
        sorted_vals = sorted(clean)
        mid = n // 2
        median_val = sorted_vals[mid] if n % 2 != 0 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0

        return ColumnStatistics(
            column_name=column_name,
            count=n,
            mean=round(mean_val, 4),
            std_dev=round(std, 4),
            min_value=min(clean),
            max_value=max(clean),
            median=round(median_val, 4)
        )
