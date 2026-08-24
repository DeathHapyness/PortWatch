"""Additional golden-file regressions for port aggregation."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from portwatch_backend.collector.parsing import build_port_entries
from portwatch_backend.core.schemas import ContainerSummary, PublishedPort

GOLDEN_FILE = Path(__file__).parents[1] / "fixtures" / "port_additional_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_FILE.read_text())


def _containers(raw_containers: list[dict[str, Any]]) -> list[ContainerSummary]:
    return [
        ContainerSummary(
            id=f"fixture-{index}",
            name=container["name"],
            image="fixture:ports",
            status="running",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ports=[PublishedPort(**port) for port in container["ports"]],
        )
        for index, container in enumerate(raw_containers)
    ]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["name"])
def test_build_port_entries_matches_additional_golden_cases(case: dict[str, Any]) -> None:
    entries = build_port_entries(_containers(case["containers"]), case["host_ports"])

    assert [entry.model_dump(mode="json") for entry in entries] == case["expected"]
