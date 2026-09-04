"""Small CLI that delegates all business logic to the package modules."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from thai_data_platform.pipeline import profile_sources, run_pipeline
from thai_data_platform.quality.checks import run_data_quality_checks
from thai_data_platform.quality.gate import evaluate_quality_gate
from thai_data_platform.warehouse import postgres


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "migrate":
        if not args.postgres_url:
            parser.error("migrate requires --postgres-url or POSTGRES_URL")
        print(postgres.run_migrations(args.postgres_url, args.migrations_dir))
        return 0
    if args.command == "profile":
        payload = profile_sources(
            ocsc_path=args.ocsc,
            cgd_path=args.cgd,
            output_path=args.output,
        )
        print(json.dumps({"sources": list(payload["sources"]), "output": str(args.output)}))
        return 0
    if args.command == "quality-fixture":
        return _quality_fixture(args.fixture)
    if args.command == "run":
        if not args.postgres_url:
            parser.error("run requires --postgres-url or POSTGRES_URL")
        result = run_pipeline(
            ocsc_path=args.ocsc,
            cgd_path=args.cgd,
            postgres_url=args.postgres_url,
            clickhouse_host=args.clickhouse_host,
            clickhouse_port=args.clickhouse_port,
            clickhouse_user=args.clickhouse_user,
            clickhouse_password=args.clickhouse_password,
            clickhouse_database=args.clickhouse_database,
            raw_root=args.raw_root,
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, default=str))
        return 0
    parser.error(f"Unsupported command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thai-data-platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate = subparsers.add_parser("migrate", help="Apply PostgreSQL migrations")
    migrate.add_argument("--postgres-url", default=os.getenv("POSTGRES_URL"))
    migrate.add_argument("--migrations-dir", default="sql/postgres")
    migrate.set_defaults(func=None)

    profile = subparsers.add_parser("profile", help="Profile source workbooks")
    profile.add_argument("--ocsc", type=Path, required=True)
    profile.add_argument("--cgd", type=Path, required=True)
    profile.add_argument("--output", type=Path, default=Path("data/processed/profile_summary.json"))

    fixture = subparsers.add_parser(
        "quality-fixture",
        help="Run the synthetic quality-gate fixture",
    )
    fixture.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/bad_data_quality.json"),
    )

    run = subparsers.add_parser("run", help="Run ingestion through analytical serving")
    run.add_argument("--ocsc", type=Path, required=True)
    run.add_argument("--cgd", type=Path, required=True)
    run.add_argument("--postgres-url", default=os.getenv("POSTGRES_URL"))
    run.add_argument("--clickhouse-host", default=os.getenv("CLICKHOUSE_HOST", "localhost"))
    run.add_argument(
        "--clickhouse-port",
        type=int,
        default=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
    )
    run.add_argument("--clickhouse-user", default=os.getenv("CLICKHOUSE_USER", "default"))
    run.add_argument("--clickhouse-password", default=os.getenv("CLICKHOUSE_PASSWORD", ""))
    run.add_argument("--clickhouse-database", default=os.getenv("CLICKHOUSE_DATABASE", "analytics"))
    run.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    return parser


def _quality_fixture(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    import pandas as pd

    fake_hash = "0" * 64
    cgd = pd.DataFrame(
        [{**row, "source_file_hash": fake_hash} for row in payload["cgd_budget_execution"]]
    )
    ocsc = pd.DataFrame(
        [{**row, "source_file_hash": fake_hash} for row in payload["ocsc_workforce"]]
    )
    issues = run_data_quality_checks(cgd, ocsc, "fixture-run", source_hashes=[fake_hash])
    gate = evaluate_quality_gate(issues)
    print(
        json.dumps(
            {"passed": gate.passed, "blocking_issue_count": gate.blocking_issue_count},
            ensure_ascii=False,
        )
    )
    return 1 if not gate.passed else 0
