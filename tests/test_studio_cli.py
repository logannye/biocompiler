"""The installed entry point opens a loopback workspace with explicit port errors."""

from contextlib import redirect_stderr
import io
import unittest
from unittest.mock import patch

from biocompiler.cli import main


class StudioCliTests(unittest.TestCase):
    def test_default_browser_and_headless_ephemeral_port(self):
        with patch("biocompiler.studio.server.serve") as serve:
            self.assertEqual(main(["studio"]), 0)
            serve.assert_called_once_with(port=8765, open_browser=True)
        with patch("biocompiler.studio.server.serve") as serve:
            self.assertEqual(main(["studio", "--port", "0", "--no-open"]), 0)
            serve.assert_called_once_with(port=0, open_browser=False)

    def test_invalid_port_and_occupied_port_are_actionable(self):
        for value in ("-1", "65536", "abc"):
            with self.subTest(value=value), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(["studio", "--port", value])
                self.assertEqual(error.exception.code, 2)
        output = io.StringIO()
        with patch("biocompiler.studio.server.serve", side_effect=OSError("Address in use")):
            with redirect_stderr(output):
                self.assertEqual(main(["studio"]), 2)
        self.assertIn("--port 0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
