from click.testing import CliRunner
from slimcraft.cli import main


def test_scan_help():
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])
    assert result.exit_code == 0
    assert "Scan a Dockerfile" in result.output


def test_harden_help():
    runner = CliRunner()
    result = runner.invoke(main, ["harden", "--help"])
    assert result.exit_code == 0
    assert "Harden a Dockerfile" in result.output


def test_verbose_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["-v", "scan", "--help"])
    assert result.exit_code == 0


def test_verbose_debug_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["-vv", "scan", "--help"])
    assert result.exit_code == 0


def test_scan_missing_file():
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "does_not_exist"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_scan_success(mock_subprocess, mock_docker, sample_dockerfile_bloated):
    runner = CliRunner()
    result = runner.invoke(main, ["scan", sample_dockerfile_bloated])
    assert result.exit_code == 0
    assert "Scan complete" in result.output
    assert "Single-stage" in result.output
    assert "node:18" in result.output


def test_harden_no_rewrite(sample_dockerfile_bloated):
    runner = CliRunner()
    result = runner.invoke(main, ["harden", sample_dockerfile_bloated])
    assert result.exit_code == 0
    assert "--rewrite flag not set" in result.output


def test_harden_rewrite_stub(sample_dockerfile_bloated):
    runner = CliRunner()
    result = runner.invoke(
        main, ["harden", sample_dockerfile_bloated, "--rewrite"]
    )
    assert result.exit_code == 0
    assert "LLM rewrite not available" in result.output


def test_harden_pr_without_rewrite(sample_dockerfile_bloated):
    runner = CliRunner()
    result = runner.invoke(
        main, ["harden", sample_dockerfile_bloated, "--pr"]
    )
    assert result.exit_code == 0
    assert "--rewrite flag not set" in result.output


def test_harden_rewrite_and_pr(sample_dockerfile_bloated):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["harden", sample_dockerfile_bloated, "--rewrite", "--pr"],
    )
    assert result.exit_code == 0
    assert "LLM rewrite not available" in result.output
