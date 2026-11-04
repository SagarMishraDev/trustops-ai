"""Phase 8 tests: deployment assets exist and are consistent."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_docker_assets():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "python:3.12" in dockerfile and "uvicorn" in dockerfile and "alembic upgrade head" in dockerfile
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "postgres:16" in compose and "DATABASE_URL" in compose and "trustops_pgdata" in compose
    assert (ROOT / ".dockerignore").exists()


def test_initial_migration_covers_all_tables():
    versions = list((ROOT / "migrations" / "versions").glob("*.py"))
    assert len(versions) == 1
    text = versions[0].read_text()
    for table in ["businesses", "conversations", "evaluations", "evaluation_issues",
                  "policies", "evidence_records", "human_reviews",
                  "benchmark_runs", "prompt_versions"]:
        assert f"'{table}'" in text, table


def test_smoke_script_and_docs_exist():
    smoke = (ROOT / "scripts" / "smoke_test.py").read_text()
    assert "signed webhook" in smoke and "SMOKE TEST PASSED" in smoke
    assert (ROOT / "docs" / "ARCHITECTURE.md").exists()
    assert (ROOT / "docs" / "DEPLOYMENT.md").exists()
