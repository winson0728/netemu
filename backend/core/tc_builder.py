from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from core.command_runner import CommandRunner, CommandResult
from core.models import Direction, validate_interface_name

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TCConfig:
    interface: str
    bandwidth_kbit: int = 0
    delay_ms: float = 0
    jitter_ms: float = 0
    loss_pct: float = 0
    duplicate_pct: float = 0
    corrupt_pct: float = 0
    disorder_pct: float = 0
    direction: Direction = Direction.egress


class TCBuilder:
    def __init__(self, runner: CommandRunner):
        self.runner = runner

    @staticmethod
    def _ifb_name(interface: str) -> str:
        return f"ifb_{interface[:11]}"

    @staticmethod
    def _has_netem(config: TCConfig) -> bool:
        return any(
            (
                config.delay_ms > 0,
                config.jitter_ms > 0,
                config.loss_pct > 0,
                config.duplicate_pct > 0,
                config.corrupt_pct > 0,
                config.disorder_pct > 0,
            )
        )

    @staticmethod
    def _has_bandwidth(config: TCConfig) -> bool:
        return config.bandwidth_kbit > 0

    def get_interfaces(self) -> list[dict]:
        result = self.runner.run(["ip", "-j", "link", "show"])
        interfaces: list[dict] = []
        if result.success and result.stdout.startswith("["):
            try:
                for item in json.loads(result.stdout):
                    name = item.get("ifname", "")
                    if name == "lo":
                        continue
                    interfaces.append(
                        {
                            "name": name,
                            "state": item.get("operstate", "UNKNOWN"),
                            "flags": item.get("flags", []),
                            "mac": item.get("address", ""),
                        }
                    )
            except json.JSONDecodeError:
                logger.warning("Could not decode `ip -j link show` output")
        if interfaces:
            return interfaces

        fallback = self.runner.run(["ip", "link", "show"])
        for line in fallback.stdout.splitlines():
            if ": " not in line or line.startswith(" "):
                continue
            _, tail = line.split(": ", 1)
            name = tail.split("@", 1)[0]
            if name == "lo":
                continue
            interfaces.append(
                {
                    "name": name,
                    "state": "UP" if "UP" in line else "DOWN",
                    "flags": [],
                    "mac": "",
                }
            )
        return interfaces

    def get_interfaces_with_stats(self) -> list[dict]:
        """Return all interfaces with stats in a single subprocess call."""
        result = self.runner.run(["ip", "-s", "-j", "link", "show"])
        interfaces: list[dict] = []
        if result.success and result.stdout.startswith("["):
            try:
                for item in json.loads(result.stdout):
                    name = item.get("ifname", "")
                    if name == "lo":
                        continue
                    stats = item.get("stats64", item.get("stats", {}))
                    rx = stats.get("rx", {})
                    tx = stats.get("tx", {})
                    interfaces.append({
                        "name": name,
                        "state": item.get("operstate", "UNKNOWN"),
                        "flags": item.get("flags", []),
                        "mac": item.get("address", ""),
                        "stats": {
                            "rx_bytes": rx.get("bytes", 0),
                            "rx_packets": rx.get("packets", 0),
                            "rx_dropped": rx.get("dropped", 0),
                            "tx_bytes": tx.get("bytes", 0),
                            "tx_packets": tx.get("packets", 0),
                            "tx_dropped": tx.get("dropped", 0),
                        },
                    })
            except json.JSONDecodeError:
                logger.warning("Could not decode `ip -s -j link show` output")
        return interfaces

    def interface_exists(self, interface: str) -> bool:
        validate_interface_name(interface)
        return any(item["name"] == interface for item in self.get_interfaces())

    def get_interface_stats(self, interface: str) -> dict:
        validate_interface_name(interface)
        result = self.runner.run(["ip", "-s", "-j", "link", "show", "dev", interface], ok_returncodes=(0, 1))
        if result.success and result.stdout.startswith("["):
            try:
                data = json.loads(result.stdout)
                if data:
                    stats = data[0].get("stats64", data[0].get("stats", {}))
                    rx = stats.get("rx", {})
                    tx = stats.get("tx", {})
                    return {
                        "rx_bytes": rx.get("bytes", 0),
                        "rx_packets": rx.get("packets", 0),
                        "rx_dropped": rx.get("dropped", 0),
                        "tx_bytes": tx.get("bytes", 0),
                        "tx_packets": tx.get("packets", 0),
                        "tx_dropped": tx.get("dropped", 0),
                    }
            except json.JSONDecodeError:
                logger.warning("Could not decode interface stats for %s", interface)
        return {
            "rx_bytes": 0,
            "rx_packets": 0,
            "rx_dropped": 0,
            "tx_bytes": 0,
            "tx_packets": 0,
            "tx_dropped": 0,
        }

    def get_current_qdisc(self, interface: str) -> str:
        validate_interface_name(interface)
        result = self.runner.run(["tc", "qdisc", "show", "dev", interface], ok_returncodes=(0, 1))
        return result.stdout

    def _run_allow_missing(self, argv: list[str]) -> CommandResult:
        return self.runner.run(argv, ok_returncodes=(0, 1, 2))

    def _build_netem_args(self, config: TCConfig) -> list[str]:
        args: list[str] = []
        if config.delay_ms > 0:
            args.extend(["delay", f"{config.delay_ms:.1f}ms"])
            if config.jitter_ms > 0:
                args.extend([f"{config.jitter_ms:.1f}ms", "distribution", "normal"])
        if config.loss_pct > 0:
            args.extend(["loss", f"{config.loss_pct:.4f}%"])
        if config.duplicate_pct > 0:
            args.extend(["duplicate", f"{config.duplicate_pct:.2f}%"])
        if config.corrupt_pct > 0:
            args.extend(["corrupt", f"{config.corrupt_pct:.2f}%"])
        if config.disorder_pct > 0:
            args.extend(["reorder", f"{config.disorder_pct:.2f}%", "25%"])
        return args

    def _build_root_chain(self, device: str, config: TCConfig) -> list[list[str]]:
        has_bw = self._has_bandwidth(config)
        has_netem = self._has_netem(config)
        commands: list[list[str]] = []
        if has_bw and has_netem:
            commands.append(["tc", "qdisc", "add", "dev", device, "root", "handle", "1:", "htb", "default", "10"])
            commands.append(
                [
                    "tc",
                    "class",
                    "add",
                    "dev",
                    device,
                    "parent",
                    "1:",
                    "classid",
                    "1:10",
                    "htb",
                    "rate",
                    f"{config.bandwidth_kbit}kbit",
                    "burst",
                    f"{max(config.bandwidth_kbit // 8, 15)}k",
                ]
            )
            commands.append(["tc", "qdisc", "add", "dev", device, "parent", "1:10", "handle", "10:", "netem", *self._build_netem_args(config)])
        elif has_bw:
            commands.append(["tc", "qdisc", "add", "dev", device, "root", "handle", "1:", "htb", "default", "10"])
            commands.append(
                [
                    "tc",
                    "class",
                    "add",
                    "dev",
                    device,
                    "parent",
                    "1:",
                    "classid",
                    "1:10",
                    "htb",
                    "rate",
                    f"{config.bandwidth_kbit}kbit",
                    "burst",
                    f"{max(config.bandwidth_kbit // 8, 15)}k",
                ]
            )
            commands.append(["tc", "qdisc", "add", "dev", device, "parent", "1:10", "handle", "10:", "pfifo"])
        elif has_netem:
            commands.append(["tc", "qdisc", "add", "dev", device, "root", "handle", "1:", "netem", *self._build_netem_args(config)])
        return commands

    def clear_rules(self, interface: str) -> dict:
        validate_interface_name(interface)
        ifb = self._ifb_name(interface)
        results = [
            self._run_allow_missing(["tc", "qdisc", "del", "dev", interface, "root"]),
            self._run_allow_missing(["tc", "qdisc", "del", "dev", interface, "ingress"]),
            self._run_allow_missing(["tc", "qdisc", "del", "dev", ifb, "root"]),
            self._run_allow_missing(["ip", "link", "set", "dev", ifb, "down"]),
            self._run_allow_missing(["ip", "link", "delete", ifb, "type", "ifb"]),
        ]
        return {
            "success": True,
            "commands": [item.command_text() for item in results],
            "errors": [],
        }

    def apply_rules(self, config: TCConfig) -> dict:
        validate_interface_name(config.interface)
        interface = config.interface
        ifb = self._ifb_name(interface)
        commands: list[list[str]] = []
        errors: list[str] = []

        self.clear_rules(interface)
        has_shape = self._has_bandwidth(config) or self._has_netem(config)
        if not has_shape:
            return {"success": True, "commands": [], "errors": []}

        if config.direction in (Direction.egress, Direction.both):
            commands.extend(self._build_root_chain(interface, config))

        if config.direction in (Direction.ingress, Direction.both):
            commands.extend(
                [
                    ["modprobe", "ifb"],
                    ["ip", "link", "add", ifb, "type", "ifb"],
                    ["ip", "link", "set", "dev", ifb, "up"],
                    ["tc", "qdisc", "add", "dev", interface, "ingress"],
                    [
                        "tc",
                        "filter",
                        "add",
                        "dev",
                        interface,
                        "parent",
                        "ffff:",
                        "protocol",
                        "all",
                        "u32",
                        "match",
                        "u32",
                        "0",
                        "0",
                        "action",
                        "mirred",
                        "egress",
                        "redirect",
                        "dev",
                        ifb,
                    ],
                ]
            )
            commands.extend(self._build_root_chain(ifb, config))

        executed: list[str] = []
        for argv in commands:
            ok_returncodes = (0,)
            if argv[:4] == ["ip", "link", "add", ifb]:
                ok_returncodes = (0, 2)
            result = self.runner.run(argv, ok_returncodes=ok_returncodes)
            executed.append(result.command_text())
            if result.returncode not in ok_returncodes:
                errors.append(f"{result.command_text()}: {result.stderr or 'command failed'}")

        return {"success": not errors, "commands": executed, "errors": errors}

    def set_disconnect(self, interface: str, disconnect: bool) -> dict:
        validate_interface_name(interface)
        chain = "FORWARD"
        comment = f"netemu_disconnect_{interface}"
        if disconnect:
            existing = self.runner.run(
                ["iptables", "-C", chain, "-i", interface, "-m", "comment", "--comment", comment, "-j", "DROP"],
                ok_returncodes=(0, 1),
            )
            if existing.returncode == 0:
                return {"success": True, "action": "already_disconnected"}
            results = [
                self.runner.run(["iptables", "-I", chain, "1", "-i", interface, "-m", "comment", "--comment", comment, "-j", "DROP"]),
                self.runner.run(["iptables", "-I", chain, "1", "-o", interface, "-m", "comment", "--comment", comment, "-j", "DROP"]),
            ]
            errors = [item.stderr for item in results if item.returncode != 0]
            return {"success": not errors, "action": "disconnected", "errors": errors}

        results = [
            self.runner.run(
                ["iptables", "-D", chain, "-i", interface, "-m", "comment", "--comment", comment, "-j", "DROP"],
                ok_returncodes=(0, 1),
            ),
            self.runner.run(
                ["iptables", "-D", chain, "-o", interface, "-m", "comment", "--comment", comment, "-j", "DROP"],
                ok_returncodes=(0, 1),
            ),
        ]
        errors = [item.stderr for item in results if item.returncode not in (0, 1)]
        return {"success": not errors, "action": "reconnected", "errors": errors}

    def set_bridge(self, lines: list[tuple[str, str]]) -> dict:
        """Set up bridge mode for the given (downlink, uplink) pairs."""
        for downlink, uplink in lines:
            validate_interface_name(downlink)
            validate_interface_name(uplink)
        errors: list[str] = []
        commands: list[list[str]] = []
        iface_names: set[str] = set()

        commands.append(["sysctl", "-w", "net.ipv4.ip_forward=0"])

        for idx, (downlink_iface, uplink_iface) in enumerate(lines, 1):
            br_name = f"br_netemu_{idx}"
            iface_names.update([downlink_iface, uplink_iface, br_name])
            commands.extend([
                ["iptables", "-t", "nat", "-D", "POSTROUTING", "-o", downlink_iface, "-j", "MASQUERADE"],
                ["ip", "link", "add", "name", br_name, "type", "bridge"],
                ["ip", "link", "set", "dev", downlink_iface, "master", br_name],
                ["ip", "link", "set", "dev", uplink_iface, "master", br_name],
                ["ip", "link", "set", "dev", br_name, "up"],
            ])

        executed: list[str] = []
        for argv in commands:
            ok_returncodes = (0,)
            if argv[:3] == ["ip", "link", "delete"] or argv[:5] == ["iptables", "-t", "nat", "-D", "POSTROUTING"]:
                ok_returncodes = (0, 1, 2)
            if argv[:4] == ["ip", "link", "add", "name"]:
                ok_returncodes = (0, 2)
            if argv[0] == "ip" and len(argv) >= 5 and argv[3] in iface_names:
                ok_returncodes = (0, 1, 2)
            if argv[0] == "ip" and len(argv) >= 5 and argv[4] in iface_names:
                ok_returncodes = (0, 1, 2)
            result = self.runner.run(argv, ok_returncodes=ok_returncodes)
            executed.append(result.command_text())
            if result.returncode not in ok_returncodes:
                errors.append(f"{result.command_text()}: {result.stderr or 'command failed'}")
        return {"success": not errors, "mode": "bridge", "commands": executed, "errors": errors}
