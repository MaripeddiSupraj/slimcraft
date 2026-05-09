import os
from slimcraft.config import getenv, _parse_dotenv


def test_getenv_default():
    assert getenv("SLIMCRAFT_NONEXISTENT", "fallback") == "fallback"


def test_getenv_from_environ():
    os.environ["SLIMCRAFT_TEST_KEY"] = "test_value"
    assert getenv("SLIMCRAFT_TEST_KEY") == "test_value"


def test_parse_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SLIMCRAFT_TEST_VAL=hello\n"
        "# comment\n"
        "SLIMCRAFT_QUOTED='world'\n"
        "\n"
    )
    _parse_dotenv(str(env_file))
    assert os.environ.get("SLIMCRAFT_TEST_VAL") == "hello"
    assert os.environ.get("SLIMCRAFT_QUOTED") == "world"
