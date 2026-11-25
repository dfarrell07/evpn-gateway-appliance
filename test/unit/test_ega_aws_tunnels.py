"""Exercise tunnel replacement without IPsec or containers, plus real timeout cleanup."""

import contextlib
import ctypes
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch


PROGRAM = (Path(__file__).resolve().parents[2] / "ansible" / "roles"
           / "evpn_onprem_appliance" / "files" / "ega_aws_tunnels.py")
SPEC = importlib.util.spec_from_file_location("ega_aws_tunnels", PROGRAM)
tunnels = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tunnels)

ARGS = ["--tunnel", "1", "169.254.10.1", "192.0.2.1",
        "--tunnel", "2", "169.254.20.1", "192.0.2.2"]
PEERS = tunnels.parse_tunnels(ARGS)
RETRY = ("Rerun deploy to retry, after restarting FRR if a deploy stopped before "
         "FRR restarted.")


class FakeHost:
    """Model Child SAs and BGP independently, recording every command and sleep."""

    def __init__(self, case, directory):
        self.case = case
        self.directory = directory
        self.children = {peer.number: peer.outside_ip for peer in PEERS}
        self.bgp = {peer.number: "Established" for peer in PEERS}
        self.events = []
        self.elapsed = 0
        self.failures = {}
        self.on_up = lambda number: None
        self.on_sleep = lambda: None

    def run(self, args):
        self.case.assertFalse((self.directory / "ega-aws.applied").exists())
        command = tuple(args)
        self.events.append(command)
        if command in self.failures:
            raise self.failures[command]
        if args == ["ipsec", "trafficstatus"]:
            return "\n".join(
                f"006 #{number}: \"ega-aws-{number}\", type=ESP, id='{outside}'"
                for number, outside in self.children.items()
            )
        if args[:4] == ["podman", "exec", "frr", "vtysh"]:
            for peer in PEERS:
                if args == ["podman", "exec", "frr", "vtysh", "-c",
                            f"show bgp neighbors {peer.inside_ip} json"]:
                    return json.dumps({peer.inside_ip: {"bgpState": self.bgp[peer.number]}})
            self.case.fail(f"Unexpected BGP command: {args}")
        if args[:2] == ["ipsec", "replace"]:
            number = int(args[-1][-1])
            self.children.pop(number, None)
            self.bgp[number] = "Idle"
            return ""
        if args[:3] == ["ipsec", "up", "--asynchronous"]:
            number = int(args[-1][-1])
            self.children[number] = PEERS[number - 1].outside_ip
            self.bgp[number] = "Established"
            self.on_up(number)
            return ""
        self.case.assertEqual(args, ["ipsec", "rereadsecrets"])
        return ""

    def sleep(self, seconds):
        self.case.assertEqual(seconds, 5)
        self.elapsed += seconds
        self.events.append(("sleep", seconds))
        self.on_sleep()

    def mutations(self):
        return [event for event in self.events if event[:2] in
                (("ipsec", "replace"), ("ipsec", "up")) or event[0] == "sleep"]


def load_events(number):
    return [("ipsec", "replace", f"ega-aws-{number}"),
            ("ipsec", "up", "--asynchronous", f"ega-aws-{number}")]


@contextlib.contextmanager
def failed_command(exception):
    """Inject a command failure while keeping process-group signals mocked."""
    with patch.object(tunnels.subprocess, "Popen") as popen, \
            patch.object(tunnels.os, "killpg") as killpg:
        process = popen.return_value.__enter__.return_value
        if isinstance(exception, OSError):
            popen.side_effect = exception
        elif isinstance(exception, subprocess.TimeoutExpired):
            process.communicate.side_effect = [exception, ("", "")] * 2
        else:
            process.communicate.side_effect = exception
        yield process, killpg


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.record = self.directory / "ega-aws.applied"
        self.record.write_text("old record\n")
        (self.directory / "ega-aws.conf").write_bytes(b"test configuration\n")
        (self.directory / "ega-aws.secrets").write_bytes(b"TEST_ONLY\n")
        self.host = FakeHost(self, self.directory)

    def deploy(self):
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = tunnels.main(ARGS, runner=self.host.run, sleep=self.host.sleep,
                                  directory=self.directory)
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn("TEST_ONLY", errors.getvalue())
        if result:
            self.assertFalse(self.record.exists())
        return result, errors.getvalue()

    def test_first_deploy_loads_both_then_waits_without_reloading(self):
        for first_ready in (1, 2):
            with self.subTest(first_ready=first_ready):
                self.host = FakeHost(self, self.directory)
                self.host.children.clear()
                self.host.bgp = {1: "Idle", 2: "Idle"}

                def on_up(number):
                    self.host.bgp[number] = "Idle"

                def on_sleep():
                    number = first_ready if self.host.elapsed == 5 else 3 - first_ready
                    self.host.bgp[number] = "Established"

                self.host.on_up = on_up
                self.host.on_sleep = on_sleep
                self.assertEqual(self.deploy(), (0, ""))
                self.assertEqual(self.host.mutations(), load_events(1) + load_events(2)
                                 + [("sleep", 5)] * 2)
                self.assertTrue(self.record.exists())

    def test_both_up_replace_one_then_wait_before_touching_two(self):
        def on_up(number):
            self.host.bgp[number] = "Idle"

        def on_sleep():
            self.host.bgp = {1: "Established", 2: "Established"}

        self.host.on_up = on_up
        self.host.on_sleep = on_sleep
        self.assertEqual(self.deploy(), (0, ""))
        self.assertEqual(self.host.mutations(), load_events(1) + [("sleep", 5)]
                         + load_events(2) + [("sleep", 5)])
        self.assertTrue(self.record.exists())

    def test_tunnel_two_down_is_replaced_first(self):
        self.host.children.pop(2)
        self.host.bgp[2] = "Idle"
        self.assertEqual(self.deploy(), (0, ""))
        self.assertEqual(self.host.mutations(), load_events(2) + load_events(1))

    def test_no_sa_still_probes_before_selecting_replacement_order(self):
        snapshots = []
        run = self.host.run

        def runner(args):
            if args == ["ipsec", "trafficstatus"]:
                if len(snapshots) < 2:
                    self.host.children.clear()
                elif len(snapshots) == 2:
                    self.host.children[1] = PEERS[0].outside_ip
                snapshots.append(self.host.children.copy())
            return run(args)

        with patch.object(self.host, "run", side_effect=runner):
            self.assertEqual(self.deploy(), (0, ""))
        self.assertEqual(snapshots[:3], [{}, {}, {1: PEERS[0].outside_ip}])
        self.assertEqual(self.host.mutations(), load_events(2) + load_events(1))
        first_load = self.host.events.index(load_events(2)[0])
        self.assertEqual(self.host.events[:first_load].count(("ipsec", "trafficstatus")), 6)

    def test_pre_wait_allows_bgp_to_recover_before_replacement(self):
        for recovery_time in (10, 45):
            with self.subTest(recovery_time=recovery_time):
                self.host = FakeHost(self, self.directory)
                self.host.bgp = {1: "Idle", 2: "Idle"}

                def on_sleep():
                    if self.host.elapsed == recovery_time:
                        self.host.bgp[1] = "Established"

                self.host.on_sleep = on_sleep
                self.assertEqual(self.deploy(), (0, ""))
                self.assertEqual(self.host.mutations(), [("sleep", 5)] * (recovery_time // 5)
                                 + load_events(2) + load_events(1))

    def test_tunnel_recovers_on_last_poll_before_loading_the_next(self):
        def on_up(number):
            if number == 1:
                self.host.bgp[number] = "Idle"

        def on_sleep():
            if self.host.elapsed == 90:
                self.host.bgp[1] = "Established"

        self.host.on_up = on_up
        self.host.on_sleep = on_sleep
        self.assertEqual(self.deploy(), (0, ""))
        self.assertEqual(self.host.mutations(), load_events(1) + [("sleep", 5)] * 18
                         + load_events(2))

    def test_pre_wait_expires_after_nine_sleeps(self):
        self.host.bgp = {1: "Idle", 2: "Idle"}
        self.assertEqual(self.deploy(), (0, ""))
        self.assertEqual(self.host.mutations(), [("sleep", 5)] * 9
                         + load_events(1) + load_events(2))

    def test_first_tunnel_timeout_stops_before_second(self):
        for child_present in (True, False):
            with self.subTest(child_present=child_present):
                self.host = FakeHost(self, self.directory)

                def on_up(number):
                    self.host.bgp[number] = "Idle"
                    if not child_present:
                        self.host.children.pop(number)

                self.host.on_up = on_up
                what = ("its BGP session with 169.254.10.1" if child_present else
                        "its Child SA with 192.0.2.1")
                self.assertEqual(self.deploy(), (1, f"ega-aws-1: {what} did not come up "
                                 f"within 90 s; stopped before any further tunnel. {RETRY}\n"))
                self.assertEqual(self.host.mutations(), load_events(1) + [("sleep", 5)] * 18)

    def test_neither_ready_after_loading_both_fails(self):
        self.host.children.clear()

        def on_up(number):
            self.host.bgp[number] = "Idle"

        self.host.on_up = on_up
        self.assertEqual(self.deploy(), (1, "Neither ega-aws-1 nor ega-aws-2 came up with "
                         f"its BGP session within 90 s. {RETRY}\n"))
        self.assertEqual(self.host.mutations(), load_events(1) + load_events(2)
                         + [("sleep", 5)] * 18)

    def test_required_command_failure_stops_immediately(self):
        for command in (("ipsec", "rereadsecrets"), *load_events(1)):
            with self.subTest(command=command):
                self.host = FakeHost(self, self.directory)
                self.host.failures[command] = tunnels.CommandError("command failed")
                self.assertEqual(self.deploy(), (1, "command failed\n"))
                self.assertEqual(self.host.events[-1], command)
                self.assertNotIn(load_events(2)[0], self.host.events)

    def test_poll_command_timeouts_are_not_ready_and_can_recover(self):
        for command in (("ipsec", "trafficstatus"),
                        ("podman", "exec", "frr", "vtysh", "-c",
                         "show bgp neighbors 169.254.10.1 json")):
            with self.subTest(command=command):
                self.host = FakeHost(self, self.directory)
                self.host.failures[command] = tunnels.CommandError("timed out after 60 s")
                self.host.on_sleep = self.host.failures.clear
                self.assertEqual(self.deploy(), (0, ""))
                self.assertTrue(self.record.exists())
                self.assertGreater(self.host.elapsed, 0)

    def test_record_format_mode_and_atomic_write_last(self):
        real_replace = os.replace
        real_fsync = os.fsync
        events = []

        def fsync(fd):
            events.append("fsync")
            self.assertFalse(self.record.exists())
            return real_fsync(fd)

        def replace(source, destination):
            events.append("replace")
            self.assertEqual(self.host.mutations(), load_events(1) + load_events(2))
            self.assertEqual(Path(source).parent, self.directory)
            self.assertEqual(destination, self.record)
            self.assertEqual(stat.S_IMODE(Path(source).stat().st_mode), 0o600)
            return real_replace(source, destination)

        with patch.object(tunnels.os, "fsync", side_effect=fsync), \
                patch.object(tunnels.os, "replace", side_effect=replace):
            self.assertEqual(self.deploy(), (0, ""))
        expected = "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path}\n"
            for path in (self.directory / "ega-aws.conf", self.directory / "ega-aws.secrets")
        )
        self.assertEqual(self.record.read_text(), expected)
        self.assertEqual(stat.S_IMODE(self.record.stat().st_mode), 0o600)
        self.assertEqual(events, ["fsync", "replace"])
        self.assertEqual(self.host.events[0], ("ipsec", "rereadsecrets"))

    def test_failed_record_write_leaves_no_record_or_temporary_file(self):
        with patch.object(tunnels.os, "replace", side_effect=OSError("rename failed")):
            result, error = self.deploy()
        self.assertEqual(result, 1)
        self.assertIn("rename failed", error)
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()),
                         ["ega-aws.conf", "ega-aws.secrets"])


class ReadinessTests(unittest.TestCase):
    def ready(self, status, bgp):
        def runner(args):
            if args == ["ipsec", "trafficstatus"]:
                return status
            self.assertEqual(args, ["podman", "exec", "frr", "vtysh", "-c",
                                   "show bgp neighbors 169.254.10.1 json"])
            return bgp

        return tunnels.Replacer(PEERS, runner=runner).ready(PEERS[0])

    def test_child_sa_requires_exact_connection_and_endpoint_id(self):
        bgp = json.dumps({PEERS[0].inside_ip: {"bgpState": "Established"}})
        for connection, outside, expected in (
                ("ega-aws-1", "192.0.2.1", True),
                ("ega-aws-1", "192.0.2.10", False),
                ("ega-aws-1", "192x0x2x1", False),
                ("ega-aws-1", "192.0.2.9", False),
                ("ega-aws-10", "192.0.2.1", False),
                ("ega-aws-2", "192.0.2.1", False)):
            with self.subTest(connection=connection, outside=outside):
                status = f'006 #1: "{connection}", type=ESP, id=\'{outside}\''
                self.assertEqual(self.ready(status, bgp), expected)
        self.assertFalse(self.ready('"ega-aws-1", id=\'192.0.2.9\'\n'
                                    '"ega-aws-2", id=\'192.0.2.1\'', bgp))

    def test_bgp_requires_expected_neighbor_and_established_json_state(self):
        status = '006 #1: "ega-aws-1", type=ESP, id=\'192.0.2.1\''
        for bgp in ("BGP state = Established", "{", "{}", "[]", "null", "42",
                    '{"169.254.10.1": null}', '{"169.254.10.1": []}',
                    '{"169.254.10.1": {}}',
                    '{"169.254.10.1": {"bgpState": "Idle"}}',
                    '{"169.254.10.1": {"bgpState": "Active"}}',
                    '{"169.254.10.1": {"bgpState": "Connect"}}',
                    '{"169.254.10.1": {"bgpState": "OpenSent"}}',
                    '{"169.254.10.1": {"bgpState": "OpenConfirm"}}',
                    '{"169.254.20.1": {"bgpState": "Established"}}'):
            with self.subTest(bgp=bgp):
                self.assertFalse(self.ready(status, bgp))

    def test_wait_ready_observes_every_poll_through_each_deadline(self):
        for peers, attempts in ((PEERS, 9), ([PEERS[0]], 18)):
            with self.subTest(attempts=attempts):
                observations = []
                elapsed = 0

                def ready(peer):
                    observations.append((elapsed, peer.number))
                    return False

                def sleep(seconds):
                    nonlocal elapsed
                    self.assertEqual(seconds, 5)
                    elapsed += seconds

                replacer = tunnels.Replacer(PEERS, sleep=sleep)
                with patch.object(replacer, "ready", side_effect=ready):
                    self.assertFalse(replacer.wait_ready(peers, attempts))
                self.assertEqual(observations, [(second, peer.number)
                                 for second in range(0, attempts * 5 + 1, 5)
                                 for peer in peers])


class CommandAndArgumentTests(unittest.TestCase):
    def test_commands_capture_output_with_a_sixty_second_timeout(self):
        command = ["ipsec", "trafficstatus"]
        for returncode in (0, 7):
            with self.subTest(returncode=returncode), \
                    patch.object(tunnels.subprocess, "Popen") as popen:
                process = popen.return_value.__enter__.return_value
                process.communicate.return_value = ("status", "ignored stderr")
                process.returncode = returncode
                if returncode:
                    with self.assertRaisesRegex(tunnels.CommandError, "exit status 7"):
                        tunnels.run_command(command)
                else:
                    self.assertEqual(tunnels.run_command(command), "status")
                popen.assert_called_once_with(command, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True,
                                              start_new_session=True)
                process.communicate.assert_called_once_with(timeout=60)

    def test_required_command_errors_include_command(self):
        command = ["ipsec", "rereadsecrets"]
        for exception, message in (
                (subprocess.TimeoutExpired(command, 60),
                 "ipsec rereadsecrets timed out after 60 s"),
                (subprocess.CalledProcessError(7, command),
                 "ipsec rereadsecrets failed (exit status 7)"),
                (FileNotFoundError("missing executable"), "ipsec rereadsecrets")):
            with self.subTest(exception=exception), \
                    failed_command(exception) as (process, killpg):
                with self.assertRaises(tunnels.CommandError) as caught:
                    tunnels.run_command(command)
                self.assertIn(message, str(caught.exception))
                self.assertNotIn("TEST_ONLY", str(caught.exception))
                if isinstance(exception, subprocess.TimeoutExpired):
                    killpg.assert_called_once_with(process.pid, signal.SIGKILL)
                    self.assertEqual(process.communicate.call_args_list, [
                        unittest.mock.call(timeout=60), unittest.mock.call()])

    def test_command_output_secrets_never_reach_errors_or_main_stderr(self):
        sentinel = "SYNTHETIC_SECRET_MUST_STAY_PRIVATE"
        for command in (["ipsec", "rereadsecrets"], *map(list, load_events(1))):
            for payload in (sentinel, sentinel.encode()):
                for stdout, stderr in ((payload, None), (None, payload)):
                    for exception in (
                            subprocess.CalledProcessError(7, command, output=stdout, stderr=stderr),
                            subprocess.TimeoutExpired(command, 60, output=stdout, stderr=stderr)):
                        with self.subTest(command=command, stdout=stdout, exception=exception), \
                                tempfile.TemporaryDirectory() as directory, \
                                failed_command(exception):
                            with self.assertRaises(tunnels.CommandError) as caught:
                                tunnels.run_command(command)
                            self.assertNotIn(sentinel, str(caught.exception))
                            errors = io.StringIO()
                            with contextlib.redirect_stderr(errors):
                                self.assertEqual(tunnels.main(ARGS, runner=tunnels.run_command,
                                                             directory=Path(directory)), 1)
                            self.assertNotIn(sentinel, errors.getvalue())

    def test_poll_command_errors_exclude_output(self):
        for command in (["ipsec", "trafficstatus"],
                        ["podman", "exec", "frr", "vtysh", "-c",
                         "show bgp neighbors 169.254.10.1 json"]):
            for exception in (
                    subprocess.CalledProcessError(7, command, output="POLL_OUTPUT",
                                                  stderr="POLL_ERROR"),
                    subprocess.TimeoutExpired(command, 60, output=b"POLL_OUTPUT",
                                              stderr=b"POLL_ERROR")):
                with self.subTest(command=command, exception=exception), \
                        failed_command(exception):
                    with self.assertRaises(tunnels.CommandError) as caught:
                        tunnels.run_command(command)
                    self.assertNotIn("POLL_", str(caught.exception))

    def test_timeout_kills_command_descendants(self):
        # Adopt and reap grandchildren even when the CI container's PID 1 does not.
        libc = ctypes.CDLL(None)
        was_subreaper = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(was_subreaper), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)  # PR_SET_CHILD_SUBREAPER
        self.addCleanup(libc.prctl, 36, was_subreaper.value, 0, 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            pidfile = Path(directory) / "children.pid"
            command = ["sh", "-c", 'sleep 30 & first=$!; sleep 30 & second=$!; '
                       'printf "%s\\n%s\\n" "$first" "$second" > "$1"; wait',
                       "timeout-test", str(pidfile)]
            try:
                with patch.object(tunnels, "COMMAND_TIMEOUT", 0.5):
                    with self.assertRaisesRegex(tunnels.CommandError, "timed out after 0.5 s"):
                        tunnels.run_command(command)
                pids = [int(pid) for pid in pidfile.read_text().splitlines()]
                self.assertEqual(len(pids), 2)
                for pid in pids:
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        try:
                            reaped, status = os.waitpid(pid, os.WNOHANG)
                        except ChildProcessError:
                            break
                        if reaped:
                            self.assertEqual(os.waitstatus_to_exitcode(status), -signal.SIGKILL)
                            break
                        time.sleep(0.01)
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
            finally:
                if pidfile.exists():
                    for pid in map(int, pidfile.read_text().splitlines()):
                        try:
                            os.kill(pid, signal.SIGKILL)
                            os.waitpid(pid, 0)
                        except (ProcessLookupError, ChildProcessError):
                            pass

    def test_arguments_accept_each_tunnel_once_and_normalize_order(self):
        self.assertEqual(tunnels.parse_tunnels(ARGS[4:] + ARGS[:4]), PEERS)

    def test_invalid_arguments_exit_one_without_running_commands(self):
        invalid = [[], ARGS[:4], ARGS[:4] * 2, ARGS + ARGS[:4],
                   ["--tunnel", "3", *ARGS[2:]],
                   [*ARGS[:2], "::1", *ARGS[3:]],
                   [*ARGS[:3], "192.0.2.999", *ARGS[4:]],
                   [*ARGS[:2], "169.254.10.1/30", *ARGS[3:]]]
        for args in invalid:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(tunnels, "run_command") as runner:
                self.assertEqual(tunnels.main(args, runner=runner), 1)
                runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
