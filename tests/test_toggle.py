import unittest
from unittest import mock

from silisten import __main__ as cli


class Toggle(unittest.TestCase):
    def test_starts_app_when_not_running(self):
        calls = []

        def fake_spawn(command):
            calls.append(("spawn", command))

        def fake_api(route, payload=None, timeout=15):
            running = any(c[0] == "spawn" for c in calls)
            if route == "/state":
                if not running:
                    raise OSError("not running")
                return {"status": "idle"}
            calls.append(("api", route))
            return {"status": "listening", "reveal": 1}

        with mock.patch.object(cli, "_already_running", side_effect=lambda: any(c[0] == "spawn" for c in calls)), \
             mock.patch.object(cli, "_spawn", side_effect=fake_spawn), \
             mock.patch.object(cli, "api", side_effect=fake_api), \
             mock.patch.object(cli.time, "sleep", lambda s: None):
            self.assertEqual(cli.cmd_toggle(None), 0)
        self.assertEqual(calls[0], ("spawn", "start"))
        self.assertEqual(calls[-1], ("api", "/toggle"))

    def test_toggles_when_running(self):
        with mock.patch.object(cli, "_already_running", return_value=True), \
             mock.patch.object(cli, "_spawn") as spawn, \
             mock.patch.object(cli, "api", return_value={"status": "listening", "reveal": 2}) as api, \
             mock.patch.object(cli.time, "sleep", lambda s: None):
            self.assertEqual(cli.cmd_toggle(None), 0)
        spawn.assert_not_called()
        api.assert_called_with("/toggle", {}, timeout=20)


if __name__ == "__main__":
    unittest.main()
