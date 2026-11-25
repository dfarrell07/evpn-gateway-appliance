"""Replace AWS IPsec tunnels one at a time, waiting for each Child SA and BGP."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


Runner = Callable[[list[str]], str]
Sleep = Callable[[float], None]
RETRY = ("Rerun deploy to retry, after restarting FRR if a deploy stopped before "
         "FRR restarted.")


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
    """An external command failed, with bounded diagnostics for required IPsec commands."""


def run_command(args: list[str]) -> str:
    """Capture one command, bounding even a stopped pluto or FRR to 60 seconds."""
    command = " ".join(args)
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True,
                              timeout=60).stdout
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
        message = (f"{command} timed out after 60 s"
                   if isinstance(error, subprocess.TimeoutExpired)
                   else f"{command} failed (exit status {error.returncode})")
        if tuple(args[:2]) in (("ipsec", "rereadsecrets"), ("ipsec", "replace"), ("ipsec", "up")):
            for output in (error.stderr, error.stdout):
                if isinstance(output, bytes):
                    output = output.decode(errors="replace")
                if output and output.strip():
                    message += f": {output.strip()[:400]}"
                    break
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
            os.fchmod(record.fileno(), 0o600)
            record.writelines(lines)
            record.flush()
            os.fsync(record.fileno())
        os.replace(temporary, directory / "ega-aws.applied")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Replacer:
    """Coordinate replacement with injectable commands and five-second sleeps."""

    def __init__(self, peers: list[Tunnel], *, runner: Runner = run_command,
                 sleep: Sleep = time.sleep, directory: Path = Path("/etc/ipsec.d")) -> None:
        self.peers = peers
        self.runner = runner
        self.sleep = sleep
        self.directory = directory

    def query(self, args: list[str]) -> str:
        """Treat failed or timed-out readiness commands as unavailable status."""
        try:
            return self.runner(args)
        except CommandError:
            return ""

    def child_up(self, peer: Tunnel) -> bool:
        """Match one connection's parsed endpoint ID exactly, on the same line."""
        for line in self.query(["ipsec", "trafficstatus"]).splitlines():
            connection = re.search(r'"([^"]+)"', line)
            if connection is None or connection[1] != peer.name:
                continue
            endpoint = re.search(r"\bid='([^']*)'", line[connection.end():])
            if endpoint is not None and endpoint[1] == peer.outside_ip:
                return True
        return False

    def ready(self, peer: Tunnel) -> bool:
        """Require a Child SA with this AWS endpoint, not one left before renumbering, and BGP Established."""
        if not self.child_up(peer):
            return False
        output = self.query(["podman", "exec", "frr", "vtysh", "-c",
                             f"show bgp neighbors {peer.inside_ip} json"])
        try:
            neighbors = json.loads(output)
        except json.JSONDecodeError:
            return False
        if not isinstance(neighbors, dict):
            return False
        neighbor = neighbors.get(peer.inside_ip)
        return isinstance(neighbor, dict) and neighbor.get("bgpState") == "Established"

    def wait_ready(self, peers: list[Tunnel], attempts: int) -> bool:
        """Poll immediately, then after at most attempts five-second sleeps."""
        for attempt in range(attempts + 1):
            if any(self.ready(peer) for peer in peers):
                return True
            if attempt < attempts:
                self.sleep(5)
        return False

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
        if '"ega-aws-' in self.query(["ipsec", "trafficstatus"]):
            self.wait_ready(self.peers, 9)
        one, two = self.peers
        loaded = False
        if not self.ready(one) and not self.ready(two):
            # Nothing is up to protect. Load both so one failed AWS endpoint
            # cannot prevent the other from starting. Libreswan keeps retrying
            # the other (auto=start), which the loop below waits for without
            # loading it again. The record needs both, so a deploy that changes
            # the connections fails until both AWS endpoints are up.
            for peer in self.peers:
                self.load(peer)
            if not self.wait_ready(self.peers, 18):
                raise RuntimeError("Neither ega-aws-1 nor ega-aws-2 came up with its "
                                   f"BGP session within 90 s. {RETRY}")
            loaded = True
            order = [peer for peer in self.peers if not self.ready(peer)]
        elif self.ready(one) and not self.ready(two):
            order = [two, one]
        else:
            order = [one, two]
        # An already-down tunnel goes first; each must be back within 90 s before
        # the next, so a bad connection change or AWS endpoint outage never
        # takes down both tunnels.
        for peer in order:
            if not loaded:
                self.load(peer)
            if not self.wait_ready([peer], 18):
                what = (f"its BGP session with {peer.inside_ip}" if self.child_up(peer)
                        else f"its Child SA with {peer.outside_ip}")
                raise RuntimeError(f"{peer.name}: {what} did not come up within 90 s; "
                                   f"stopped before any further tunnel. {RETRY}")
        # Deploy replaces the tunnels again until this record matches (tasks/ipsec.yml).
        write_record(self.directory)


def main(argv: list[str] | None = None, *, runner: Runner = run_command,
         sleep: Sleep = time.sleep, directory: Path = Path("/etc/ipsec.d")) -> int:
    """Validate arguments and report failures to stderr."""
    try:
        peers = parse_tunnels(argv)
    except SystemExit as error:
        return 0 if error.code == 0 else 1
    try:
        Replacer(peers, runner=runner, sleep=sleep, directory=directory).apply()
    except (RuntimeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
