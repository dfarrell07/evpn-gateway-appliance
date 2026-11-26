"""Replace AWS IPsec tunnels one at a time, waiting for each Child SA and BGP."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import fcntl
from functools import partial
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time


Runner = Callable[[list[str]], str]
Sleep = Callable[[float], None]
Clock = Callable[[], float]
COMMAND_TIMEOUT = 60
POLL_TIMEOUT = 5
RETRY = ("Rerun deploy to retry, after restarting FRR if a deploy stopped before "
         "FRR restarted.")
NO_REPLACE = ("ipsec trafficstatus or vtysh did not answer within 5 s, so no connection "
              "was replaced. Rerun deploy.")


class Readiness(Enum):
    """Distinguish an answered status from an unavailable poll."""

    READY = "ready"
    NOT_READY = "not ready"
    UNKNOWN = "unknown"


def confirmed_ready(state: Readiness) -> bool:
    """Require an answered decision before the first connection is replaced."""
    if state is Readiness.UNKNOWN:
        raise RuntimeError(NO_REPLACE)
    return state is Readiness.READY


@dataclass(frozen=True)
class Tunnel:
    """Non-secret addresses of one numbered appliance connection."""

    number: int
    inside_ip: str
    outside_ip: str

    @property
    def name(self) -> str:
        """Return the Libreswan connection name."""
        return f"ega-aws-{self.number}"


class CommandError(RuntimeError):
    """An external command failed with only safe diagnostics."""


def run_command(args: list[str], *, lock_fd: int | None = None) -> str:
    """Bound polls to 5 s and mutations to 60 s; expose only replace/up stderr."""
    command = " ".join(args)
    polling = (args == ["ipsec", "trafficstatus"]
               or args[:4] == ["podman", "exec", "frr", "vtysh"])
    timeout = POLL_TIMEOUT if polling else COMMAND_TIMEOUT
    try:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, errors="replace", start_new_session=True,
                              # Only changes keep the lock; a stuck poll must not block later deploys.
                              pass_fds=() if lock_fd is None or polling else (lock_fd,)) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    stderr = process.communicate(timeout=5)[1]
                except subprocess.TimeoutExpired:
                    pass
                else:
                    error.stderr = stderr or error.stderr
                raise
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, args, stderr=stderr)
            return stdout
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
        message = (f"{command} timed out after {error.timeout} s"
                   if isinstance(error, subprocess.TimeoutExpired)
                   else f"{command} failed (exit status {error.returncode})")
        if args[:2] == ["ipsec", "rereadsecrets"]:
            # Libreswan can echo secrets in its errors, so point to its log instead.
            message += "; its output is withheld, see journalctl -u ipsec"
        elif args[:2] in (["ipsec", "replace"], ["ipsec", "up"]):
            detail = error.stderr or ""
            if isinstance(detail, bytes):
                detail = detail.decode(errors="replace")
            if detail.strip():
                message += f": {detail.strip()[:400]}"
        raise CommandError(message) from error
    except OSError as error:
        raise CommandError(f"{command} could not run: {error.strerror}") from error


def parse_tunnels(argv: list[str] | None) -> list[Tunnel]:
    """Validate both IPv4 tunnel triples and return them in tunnel order."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tunnel", action="append", nargs=3, required=True,
                        metavar=("N", "INSIDE", "OUTSIDE"))
    args = parser.parse_args(argv)
    if len(args.tunnel) != 2 or {item[0] for item in args.tunnel} != {"1", "2"}:
        parser.error("--tunnel must specify each of 1 and 2 exactly once")
    peers = []
    for number, inside, outside in args.tunnel:
        try:
            peers.append(Tunnel(int(number), str(ipaddress.IPv4Address(inside)),
                                str(ipaddress.IPv4Address(outside))))
        except ipaddress.AddressValueError:
            parser.error(f"tunnel {number} requires IPv4 inside and outside addresses")
    return sorted(peers, key=lambda peer: peer.number)


def write_record(directory: Path) -> None:
    """Atomically publish sha256sum-compatible hashes with mode 0600."""
    lines = []
    for name in ("ega-aws.conf", "ega-aws.secrets"):
        path = directory / name
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        lines.append(f"{digest}  {path}\n")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=directory,
                                         prefix=".ega-aws.applied.", delete=False) as record:
            temporary = Path(record.name)
            record.writelines(lines)
            record.flush()
            os.fsync(record.fileno())
        os.replace(temporary, directory / "ega-aws.applied")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Replacer:
    """Coordinate replacement with injectable commands, clock and sleep."""

    def __init__(self, peers: list[Tunnel], *, runner: Runner = run_command,
                 sleep: Sleep = time.sleep, monotonic: Clock = time.monotonic,
                 directory: Path = Path("/etc/ipsec.d")) -> None:
        self.peers = peers
        self.runner = runner
        self.sleep = sleep
        self.monotonic = monotonic
        self.directory = directory

    def query(self, args: list[str]) -> str | None:
        """Treat failed or timed-out readiness commands as unavailable status."""
        try:
            return self.runner(args)
        except CommandError:
            return None

    def child_up(self, peer: Tunnel) -> Readiness:
        """Match one connection's parsed endpoint ID exactly, on the same line."""
        output = self.query(["ipsec", "trafficstatus"])
        if output is None:
            return Readiness.UNKNOWN
        for line in output.splitlines():
            connection = re.search(r'"([^"]+)"', line)
            if connection is None or connection[1] != peer.name:
                continue
            endpoint = re.search(r"\bid='([^']*)'", line[connection.end():])
            if endpoint is not None and endpoint[1] == peer.outside_ip:
                return Readiness.READY
        return Readiness.NOT_READY

    def ready(self, peer: Tunnel) -> Readiness:
        """Require a Child SA with this AWS endpoint, not one left before renumbering, and BGP Established."""
        child = self.child_up(peer)
        if child is not Readiness.READY:
            return child
        output = self.query(["podman", "exec", "frr", "vtysh", "-c",
                             f"show bgp neighbors {peer.inside_ip} json"])
        if output is None:
            return Readiness.UNKNOWN
        try:
            neighbors = json.loads(output)
        except json.JSONDecodeError:
            return Readiness.NOT_READY
        if not isinstance(neighbors, dict):
            return Readiness.NOT_READY
        neighbor = neighbors.get(peer.inside_ip)
        return (Readiness.READY if isinstance(neighbor, dict)
                and neighbor.get("bgpState") == "Established" else Readiness.NOT_READY)

    def wait_ready(self, peers: list[Tunnel], timeout: float) -> Readiness:
        """Poll immediately and through the deadline, counting command time too."""
        deadline = self.monotonic() + timeout
        while True:
            state = Readiness.NOT_READY
            for peer in peers:
                observed = self.ready(peer)
                if observed is Readiness.READY:
                    return Readiness.READY
                if observed is Readiness.UNKNOWN:
                    state = Readiness.UNKNOWN
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                return state
            self.sleep(min(5, remaining))

    def load(self, peer: Tunnel) -> None:
        """Replace and initiate one connection, stopping on either failure."""
        self.runner(["ipsec", "replace", peer.name])
        self.runner(["ipsec", "up", "--asynchronous", peer.name])

    def apply(self) -> None:
        """Invalidate first; record only after both tunnels have recovered."""
        # From here pluto may hold keys or connections no file matches.
        (self.directory / "ega-aws.applied").unlink(missing_ok=True)
        self.runner(["ipsec", "rereadsecrets"])
        # A bad key, loaded for both by rereadsecrets, still reaches the other
        # tunnel at its next re-authentication.
        # An FRR restart just before this handler drops both BGP sessions. While
        # any tunnel has a Child SA, wait up to 45 s (AWS's 30 s hold time plus
        # FRR's 10 s connect retry) for one to be ready before choosing.
        status = self.query(["ipsec", "trafficstatus"])
        if status is None:
            raise RuntimeError(NO_REPLACE)
        timeout = 45 if '"ega-aws-' in status else 0
        confirmed_ready(self.wait_ready(self.peers, timeout))
        one, two = self.peers
        loaded = False
        if not confirmed_ready(self.ready(one)) and not confirmed_ready(self.ready(two)):
            # Nothing is up to protect. Load both so one failed AWS endpoint
            # cannot prevent the other from starting. Libreswan keeps retrying
            # the other (auto=start), which the loop below waits for without
            # loading it again. The record needs both, so a deploy that changes
            # the connections fails until both AWS endpoints are up.
            for peer in self.peers:
                self.load(peer)
            if self.wait_ready(self.peers, 90) is not Readiness.READY:
                raise RuntimeError("Neither ega-aws-1 nor ega-aws-2 came up with its "
                                   f"BGP session within 90 s. {RETRY}")
            loaded = True
            order = [peer for peer in self.peers if self.ready(peer) is not Readiness.READY]
        elif confirmed_ready(self.ready(one)) and not confirmed_ready(self.ready(two)):
            order = [two, one]
        else:
            order = [one, two]
        # An already-down tunnel goes first; each must be back within 90 s before
        # the next, so a bad connection change or AWS endpoint outage never
        # takes down both tunnels.
        for peer in order:
            if not loaded:
                self.load(peer)
            if self.wait_ready([peer], 90) is not Readiness.READY:
                what = (f"its BGP session with {peer.inside_ip}"
                        if self.child_up(peer) is Readiness.READY
                        else f"its Child SA with {peer.outside_ip}")
                raise RuntimeError(f"{peer.name}: {what} did not come up within 90 s; "
                                   f"stopped before any further tunnel. {RETRY}")
        # Deploy replaces the tunnels again until this record matches (tasks/ipsec.yml).
        write_record(self.directory)


def main(argv: list[str] | None = None, *, runner: Runner | None = None,
         sleep: Sleep = time.sleep, monotonic: Clock = time.monotonic,
         directory: Path = Path("/etc/ipsec.d")) -> int:
    """Validate arguments and report failures to stderr."""
    try:
        peers = parse_tunnels(argv)
    except SystemExit as error:
        return 0 if error.code == 0 else 1
    try:
        with (directory / "ega-aws.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("another replacement of the AWS IPsec connections is still "
                                   "running (or an ipsec command it started is stuck); rerun "
                                   "deploy after it finishes, or see the evpn_onprem_appliance "
                                   "README if it persists") from error
            # Surviving commands must keep the lock if this parent is terminated.
            if runner is None:
                runner = partial(run_command, lock_fd=lock.fileno())
            Replacer(peers, runner=runner, sleep=sleep, monotonic=monotonic,
                     directory=directory).apply()
    except (RuntimeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
