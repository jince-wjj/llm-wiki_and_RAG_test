"""Orchestrator: run phases sequentially, skipping completed ones.

Usage:
    python -m src.run_experiment              # run from latest checkpoint
    python -m src.run_experiment --from 3     # force re-run from Phase 3

Each phase is idempotent and resumable. Phases that have written
checkpoints/phaseN_done are skipped.
"""

from __future__ import annotations

import argparse
import sys

from . import (
    benchmark_gen,
    data_prep,
    rag_ingest,
    rag_query,
    utils,
    wiki_ingest,
    wiki_query,
)


PHASES = [
    (1, "data_prep", data_prep.run),
    (2, "benchmark_gen", benchmark_gen.run),
    (3, "wiki_ingest", wiki_ingest.run),
    (4, "rag_ingest", rag_ingest.run),
    (5, "rag_query", rag_query.run),
    (6, "wiki_query", wiki_query.run),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_phase", type=int, default=None)
    args = ap.parse_args()

    for n, name, fn in PHASES:
        if args.from_phase is not None and n < args.from_phase:
            continue
        # The query phases share checkpoint logic with their feeder phases
        # but we use a marker per phase. RAG query has no marker; we just
        # check that results file exists.
        if name == "rag_query":
            from . import config
            if config.RAG_ANSWERS_JSON.exists():
                print(f"Phase {n} ({name}) already has output, skipping.")
                continue
        elif name == "wiki_query":
            from . import config
            if config.WIKI_ANSWERS_JSON.exists():
                print(f"Phase {n} ({name}) already has output, skipping.")
                continue
        else:
            if utils.checkpoint_exists(f"phase{n}_done") or utils.checkpoint_exists(
                f"phase{n}_done.json"
            ):
                print(f"Phase {n} ({name}) checkpoint exists, skipping.")
                continue
        print(f"=== Phase {n}: {name} ===")
        fn()


if __name__ == "__main__":
    main()
