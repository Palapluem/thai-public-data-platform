"""Small CLI that delegates all business logic to the package modules."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from thai_data_platform.pipeline import profile_sources, run_pipeline
from thai_data_platform.public_sources.dashboard import build_public_dashboard
from thai_data_platform.public_sources.pipeline import run_public_pipeline
from thai_data_platform.public_sources.readers import (
    load_public_source_specs,
    parse_public_source,
    write_canonical_parquet,
)
from thai_data_platform.quality.checks import run_data_quality_checks
from thai_data_platform.quality.gate import evaluate_quality_gate
from thai_data_platform.warehouse import postgres


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
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
            schema_contract_path=args.schema_contract,
            run_type=args.run_type,
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, default=str))
        return 0
    if args.command == "public-run":
        if not args.postgres_url:
            parser.error("public-run requires --postgres-url or POSTGRES_URL")
        result = run_public_pipeline(
            postgres_url=args.postgres_url,
            clickhouse_host=args.clickhouse_host,
            clickhouse_port=args.clickhouse_port,
            clickhouse_user=args.clickhouse_user,
            clickhouse_password=args.clickhouse_password,
            clickhouse_database=args.clickhouse_database,
            source_config_path=args.source_config,
            migrations_dir=args.migrations_dir,
            serving_migrations_dir=args.serving_migrations_dir,
            query_dir=args.query_dir,
            run_type=args.run_type,
            source_ids=set(args.source_id) if args.source_id else None,
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, default=str))
        return 0
    if args.command == "public-dashboard":
        if not args.postgres_url:
            parser.error("public-dashboard requires --postgres-url or POSTGRES_URL")
        result = build_public_dashboard(
            postgres_url=args.postgres_url,
            clickhouse_host=args.clickhouse_host,
            clickhouse_port=args.clickhouse_port,
            clickhouse_user=args.clickhouse_user,
            clickhouse_password=args.clickhouse_password,
            clickhouse_database=args.clickhouse_database,
            output_path=args.output,
        )
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    if args.command == "public-parquet":
        specs = load_public_source_specs(
            args.source_config,
            source_ids={args.source_id},
        )
        if len(specs) != 1:
            parser.error(f"Expected one enabled source for --source-id {args.source_id}")
        result = write_canonical_parquet(parse_public_source(specs[0]), args.output)
        print(json.dumps({"output": str(result)}, ensure_ascii=False))
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
    run.add_argument(
        "--schema-contract",
        type=Path,
        default=Path(os.getenv("SCHEMA_CONTRACT", "config/schema_contracts.json")),
    )
    run.add_argument(
        "--run-type",
        choices=["manual", "scheduled", "backfill", "replay"],
        default=os.getenv("PIPELINE_RUN_TYPE", "manual"),
        help="Operational intent recorded in ops.pipeline_run",
    )

    public_run = subparsers.add_parser(
        "public-run",
        help="Run the multi-format public-source pipeline",
    )
    _add_public_connection_args(public_run)
    public_run.add_argument(
        "--source-config",
        type=Path,
        default=Path(os.getenv("PUBLIC_SOURCE_CONFIG", "config/public_sources.yml")),
    )
    public_run.add_argument("--migrations-dir", type=Path, default=Path("sql/postgres"))
    public_run.add_argument(
        "--serving-migrations-dir",
        type=Path,
        default=Path("sql/clickhouse"),
    )
    public_run.add_argument(
        "--query-dir",
        type=Path,
        default=Path("analytics/queries/public"),
    )
    public_run.add_argument(
        "--source-id",
        action="append",
        help="Restrict the run to one or more registered source IDs",
    )
    public_run.add_argument(
        "--run-type",
        choices=["manual", "scheduled", "backfill", "replay"],
        default=os.getenv("PUBLIC_PIPELINE_RUN_TYPE", "scheduled"),
    )

    dashboard = subparsers.add_parser(
        "public-dashboard",
        help="Build the self-contained public analytical dashboard",
    )
    _add_public_connection_args(dashboard)
    dashboard.add_argument(
        "--output",
        type=Path,
        default=Path(
            os.getenv("PUBLIC_DASHBOARD_OUTPUT", "data/processed/public_dashboard/index.html")
        ),
    )

    parquet = subparsers.add_parser(
        "public-parquet",
        help="Materialize one canonical source as Parquet",
    )
    parquet.add_argument(
        "--source-config",
        type=Path,
        default=Path(os.getenv("PUBLIC_SOURCE_CONFIG", "config/public_sources.yml")),
    )
    parquet.add_argument("--source-id", required=True)
    parquet.add_argument(
        "--output",
        type=Path,
        default=Path(
            "datasets/public/derived/labour/nso_labour_region_sex_2569.parquet"
        ),
    )
    return parser


def _add_public_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--postgres-url", default=os.getenv("POSTGRES_URL"))
    parser.add_argument("--clickhouse-host", default=os.getenv("CLICKHOUSE_HOST", "localhost"))
    parser.add_argument(
        "--clickhouse-port",
        type=int,
        default=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
    )
    parser.add_argument("--clickhouse-user", default=os.getenv("CLICKHOUSE_USER", "default"))
    parser.add_argument("--clickhouse-password", default=os.getenv("CLICKHOUSE_PASSWORD", ""))
    parser.add_argument(
        "--clickhouse-database",
        default=os.getenv("CLICKHOUSE_DATABASE", "analytics"),
    )


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
