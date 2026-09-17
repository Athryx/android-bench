from unittest.mock import patch

from android_bench.cli import callback


def test_callback_loads_dotenv() -> None:
    with patch("android_bench.cli.load_dotenv") as load_dotenv:
        callback()

    load_dotenv.assert_called_once_with()
