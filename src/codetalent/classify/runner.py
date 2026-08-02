"""Batch classification runner: enriched metadata parquet -> spec 9.3 parquet.

Reads the Milestone C enrichment output (spec 9.2 repository metadata) and the
discovery activity summary (spec 9.1, for ``single_actor_event_share``), joins
them on ``repo_name``, classifies every metadata row with the deterministic
rule classifier, and writes a spec 9.3 parquet whose rows validate through
:class:`codetalent.schemas.RepositoryClassification`.

Deterministic: rows are classified independently and written sorted by
``repo_name``, so identical inputs always produce an identical output table.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from codetalent.classify.repository_classifier import classify_repository
from codetalent.config import AtlasConfig, ConfigError
from codetalent.schemas import ClassificationStatus, RepositoryClassification, RepositoryMetadata

# Spec 9.3 column contract, in declaration order.
CLASSIFICATION_COLUMNS: tuple[str, ...] = tuple(RepositoryClassification.model_fields)

_STRING_LIST = pa.list_(pa.string())
_OUTPUT_SCHEMA = pa.schema(
    [
        pa.field("repo_name", pa.string(), nullable=False),
        pa.field("domain_id", pa.string(), nullable=False),
        pa.field("subdomains", _STRING_LIST, nullable=False),
        pa.field("classification_score", pa.float64(), nullable=False),
        pa.field("classification_status", pa.string(), nullable=False),
        pa.field("evidence_topics", _STRING_LIST, nullable=False),
        pa.field("evidence_terms", _STRING_LIST, nullable=False),
        pa.field("evidence_files", _STRING_LIST, nullable=False),
        pa.field("negative_evidence", _STRING_LIST, nullable=False),
        pa.field("manual_label", pa.string(), nullable=True),
        pa.field("manual_notes", pa.string(), nullable=True),
    ]
)


@dataclass(frozen=True)
class ClassificationRunSummary:
    """Counts and output location of one classification run."""

    total: int
    accepted: int
    rejected: int
    borderline: int
    output_path: Path


def _single_actor_shares(activity_path: Path) -> dict[str, float | None]:
    """Map repo_name -> single_actor_event_share from the activity summary."""
    table = pq.read_table(activity_path, columns=["repo_name", "single_actor_event_share"])
    shares: dict[str, float | None] = {}
    for row in table.to_pylist():
        repo_name = row["repo_name"]
        share = row["single_actor_event_share"]
        shares[str(repo_name)] = float(share) if share is not None else None
    return shares


def classify_repositories(
    config: AtlasConfig,
    domain_id: str,
    metadata_path: Path,
    activity_path: Path,
    output_path: Path,
) -> ClassificationRunSummary:
    """Classify every enriched repository and write the spec 9.3 parquet.

    Repositories missing from the activity summary are classified without a
    dominance check (their ``single_actor_event_share`` is unknown, and the
    classifier never fabricates it).
    """
    if domain_id not in config.taxonomies:
        raise ConfigError(
            f"unknown domain_id {domain_id!r}: configured taxonomies are "
            f"{sorted(config.taxonomies)}"
        )
    taxonomy = config.taxonomies[domain_id]
    weights = config.scoring.classification
    filters = config.repo_filters

    metadata_table = pq.read_table(metadata_path, columns=list(RepositoryMetadata.model_fields))
    shares = _single_actor_shares(activity_path)

    results: list[RepositoryClassification] = []
    for row in metadata_table.to_pylist():
        metadata = RepositoryMetadata.model_validate(row)
        results.append(
            classify_repository(
                metadata,
                taxonomy,
                weights,
                filters=filters,
                single_actor_event_share=shares.get(metadata.repo_name),
            )
        )

    results.sort(key=lambda record: record.repo_name)
    records = [record.model_dump(mode="json") for record in results]
    output_table = pa.Table.from_pylist(records, schema=_OUTPUT_SCHEMA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(output_table, output_path)

    by_status = dict.fromkeys(ClassificationStatus, 0)
    for record in results:
        by_status[record.classification_status] += 1
    return ClassificationRunSummary(
        total=len(results),
        accepted=by_status[ClassificationStatus.ACCEPTED],
        rejected=by_status[ClassificationStatus.REJECTED],
        borderline=by_status[ClassificationStatus.BORDERLINE],
        output_path=output_path,
    )
