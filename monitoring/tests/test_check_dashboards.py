"""Unit tests for monitoring/check_dashboards.py: each case breaks one rule the checker enforces."""
import copy
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import check_dashboards  # noqa: E402

SCOPED = '{job=~"$job", instance=~"$instance"}'
DATASOURCE = {"type": "prometheus", "uid": "${datasource}"}
DASHBOARD = {
    "templating": {"list": [
        {"name": "datasource", "type": "datasource", "query": "prometheus"},
        {"name": "job", "type": "query", "datasource": DATASOURCE, "query": "label_values(frrk8s_scrape_success, job)"},
        {"name": "instance", "type": "query", "datasource": DATASOURCE,
         "query": "label_values(frrk8s_scrape_success, instance)"},
    ]},
    "panels": [{"id": 1, "datasource": DATASOURCE, "targets": [
        {"refId": "A", "expr": f"sum by (job, instance) (frrk8s_bgp_session_up{SCOPED})"}]}],
}


class CheckDashboardsTest(unittest.TestCase):
    def check(self, dashboard):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(dashboard, f)
            f.flush()
            return check_dashboards.check_dashboard(f.name)

    def broken(self, expr=None, **panel):
        dashboard = copy.deepcopy(DASHBOARD)
        if expr is not None:
            dashboard["panels"][0]["targets"][0]["expr"] = expr
        dashboard["panels"][0].update(panel)
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        return str(error.exception)

    def test_valid_dashboard_passes(self):
        self.assertEqual(self.check(DASHBOARD), "1 queries OK")

    def test_label_value_that_looks_like_a_series_passes(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["panels"][0]["targets"][0]["expr"] = (
            'frrk8s_bgp_session_up{job=~"$job", instance=~"$instance", peer="frrk8s_x up"}')
        self.assertEqual(self.check(dashboard), "1 queries OK")

    def test_unscoped_selector_fails(self):
        self.assertIn("lacks", self.broken("frrk8s_bgp_session_up"))
        self.assertIn("lacks", self.broken(f"frrk8s_bgp_session_up{SCOPED} and up"))
        self.assertIn("lacks", self.broken('frrk8s_bgp_session_up{job=~"$job"}'))

    def test_unscoped_node_selector_fails(self):
        self.assertIn("node_network_info lacks", self.broken(f"frrk8s_bgp_session_up{SCOPED} and on() node_network_info"))

    def test_name_matcher_fails(self):
        self.assertIn("__name__", self.broken('{__name__=~"frrk8s_.*", job=~"$job", instance=~"$instance"}'))

    def test_unknown_series_fails(self):
        self.assertIn("unknown frr-k8s series", self.broken(f"frrk8s_bgp_sesion_up{SCOPED}"))

    def test_invalid_promql_fails(self):
        self.assertIn("invalid PromQL", self.broken(f"rate(frrk8s_bgp_updates_total{SCOPED})"))

    def test_wrong_datasource_fails(self):
        self.assertIn("datasource", self.broken(datasource={"type": "prometheus", "uid": "other"}))

    def test_duplicate_panel_id_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["panels"].append(copy.deepcopy(dashboard["panels"][0]))
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("duplicate panel id", str(error.exception))

    def test_panel_in_collapsed_row_is_checked(self):
        dashboard = copy.deepcopy(DASHBOARD)
        nested = copy.deepcopy(dashboard["panels"][0])
        nested.update(id=3, targets=[{"refId": "A", "expr": "frrk8s_bgp_session_up"}])
        dashboard["panels"].append({"id": 2, "type": "row", "panels": [nested]})
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("panel 3", str(error.exception))

    def test_missing_panel_id_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        del dashboard["panels"][0]["id"]
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("missing or duplicate panel id", str(error.exception))

    def test_wrong_datasource_variable_type_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["templating"]["list"][0]["type"] = "custom"
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("datasource variable", str(error.exception))

    def test_wrong_datasource_variable_query_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["templating"]["list"][0]["query"] = "loki"
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("datasource variable", str(error.exception))

    def test_variable_on_other_datasource_fails(self):
        for name in ("job", "instance"):
            with self.subTest(variable=name):
                dashboard = copy.deepcopy(DASHBOARD)
                variable = next(v for v in dashboard["templating"]["list"] if v["name"] == name)
                variable["datasource"] = {"type": "prometheus", "uid": "other"}
                with self.assertRaises(ValueError) as error:
                    self.check(dashboard)
                self.assertIn("job and instance", str(error.exception))

    def test_string_datasource_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["templating"]["list"][1]["datasource"] = "${datasource}"
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("job and instance", str(error.exception))

    def test_missing_variable_fails(self):
        for name in ("job", "instance"):
            with self.subTest(variable=name):
                dashboard = copy.deepcopy(DASHBOARD)
                dashboard["templating"]["list"] = [v for v in dashboard["templating"]["list"] if v["name"] != name]
                with self.assertRaises(ValueError) as error:
                    self.check(dashboard)
                self.assertIn("job and instance", str(error.exception))

    def test_target_datasource_override_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["panels"][0]["targets"][0]["datasource"] = {"type": "prometheus", "uid": "other"}
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("datasource", str(error.exception))

    def test_unknown_series_in_variable_fails(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["templating"]["list"][1]["query"] = "label_values(frrk8s_made_up, job)"
        with self.assertRaises(ValueError) as error:
            self.check(dashboard)
        self.assertIn("variable job", str(error.exception))

    def test_backtick_label_value_is_ignored(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["panels"][0]["targets"][0]["expr"] = (
            'frrk8s_bgp_session_up{job=~"$job", instance=~"$instance", peer=`up frrk8s_x`}')
        self.assertEqual(self.check(dashboard), "1 queries OK")

    def test_missing_expr_fails(self):
        self.assertIn("no expr", self.broken(""))

    def test_rules_with_unknown_series_fail(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
            f.write("expr: frrk8s_bgp_session_up == 0 or frrk8s_made_up == 1\n")
            f.flush()
            with self.assertRaises(ValueError) as error:
                check_dashboards.check_rules(f.name)
            self.assertIn("frrk8s_made_up", str(error.exception))


class ApplianceDashboardTest(unittest.TestCase):
    """The appliance dashboard's device filters must match the devices the on-prem role creates."""

    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        with open(os.path.join(root, "monitoring", "dashboards", "appliance.json")) as f:
            dashboard = json.load(f)
        queries = [t["expr"] for p in check_dashboards.panels(dashboard["panels"]) for t in p.get("targets", [])]
        queries += [json.dumps(v.get("query", "")) for v in dashboard["templating"]["list"]]
        self.regexes = {m for q in queries for m in re.findall(r'device=~\\?"([^"\\]+)', q)}
        role = os.path.join(root, "ansible", "roles", "evpn_onprem_appliance")
        with open(os.path.join(role, "templates", "nmstate.yml.j2")) as f:
            # Interfaces the role creates; the {{ iface }} entries detach or remove leftovers.
            names = [n for n in re.findall(r"^  - name: (.+?)\s*$", f.read(), re.M) if "iface" not in n]
        with open(os.path.join(role, "tasks", "main.yml")) as f:
            names += re.findall(r"/etc/wireguard/(\w+)\.conf", f.read())[:1]
        self.devices = [n.replace("{{ s.vlan }}", "100").replace("{{ vni }}", "10100") for n in names]

    def test_role_creates_the_expected_devices(self):
        self.assertEqual(sorted(re.sub(r"\d+", "N", d) for d in self.devices),
                         ["br-vniN", "trunk-br", "trunk.N", "vxlanN", "wgN"])

    def test_every_device_filter_matches_role_devices(self):
        bridges = {"trunk-br"} | {d for d in self.devices if d.startswith("br-vni")}
        expected = {
            "all": set(self.devices),
            "non-bridge": set(self.devices) - bridges,
            "selector": {d for d in self.devices if d.startswith(("vxlan", "wg"))},
        }
        self.assertEqual(len(self.regexes), 3, self.regexes)
        for regex in self.regexes:
            matched = {d for d in self.devices if re.fullmatch(regex, d)}
            self.assertIn(matched, expected.values(), f"{regex} matches {sorted(matched)}")


if __name__ == "__main__":
    unittest.main()
