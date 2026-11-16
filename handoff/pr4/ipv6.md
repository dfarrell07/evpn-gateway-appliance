**Is this a BUG FIX or a FEATURE ?**:

/kind bug

**What this PR does / why we need it**:

`frr-metrics --metrics-bind-address=::1` exits with `listen tcp: address ::1:9141: too many colons in address`, because the exporter joins host and port with `"%s:%d"`. The out-of-cluster README tells operators to bind to loopback or a management address, and on an IPv6 network that is a bare IPv6 address. This joins them with `net.JoinHostPort` and still accepts the bracketed form (`[::1]`) that works today. The shipped manifests bind `0.0.0.0`, which already listens dual-stack, so in-cluster deployments are unaffected.

**Special notes for your reviewer**:

CodeRabbit raised this on #528, which does not touch the bind address, so it is fixed here instead. The tests cover IPv4, hostnames, an empty host, zones and both IPv6 forms, plus a real `[::1]` listener that skips without IPv6. Same class of fix as metallb/metallb#239.

**Release note**:

```release-note
frr-metrics now accepts a bare IPv6 address in --metrics-bind-address.
```

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
