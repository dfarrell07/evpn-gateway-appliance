"""Unit tests for monitoring/check_dashboards.py: each case breaks one rule the checker enforces."""
import contextlib
import copy
import io
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
    def test_main_returns_failure(self):
        unscoped = copy.deepcopy(DASHBOARD)
        unscoped["panels"][0]["targets"][0]["expr"] = "frrk8s_bgp_session_up"
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, "good.json"), os.path.join(d, "bad.json")
            for path, dashboard in ((good, DASHBOARD), (bad, unscoped)):
                with open(path, "w") as f:
                    json.dump(dashboard, f)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(check_dashboards.main([good]))
                self.assertTrue(check_dashboards.main([good, bad]))

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
        self.assertEqual(self.check(DASHBOARD)[0], "1 panels, 1 PromQL queries OK")

    def test_label_value_that_looks_like_a_series_passes(self):
        dashboard = copy.deepcopy(DASHBOARD)
        dashboard["panels"][0]["targets"][0]["expr"] = (
            'frrk8s_bgp_session_up{job=~"$job", instance=~"$instance", peer="frrk8s_x up"}')
        self.assertEqual(self.check(dashboard)[0], "1 panels, 1 PromQL queries OK")

    def test_unscoped_selector_fails(self):
        self.assertIn("lacks", self.broken("frrk8s_bgp_session_up"))
        self.assertIn("lacks", self.broken(f"frrk8s_bgp_session_up{SCOPED} and up"))
        self.assertIn("lacks", self.broken('frrk8s_bgp_session_up{job=~"$job"}'))

    def test_unscoped_node_selector_fails(self):
        self.assertIn("node_network_info lacks", self.broken(f"frrk8s_bgp_session_up{SCOPED} and on() node_network_info"))

    def test_unscoped_probe_selector_fails(self):
        self.assertIn("ega_path_probe_success lacks",
                      self.broken(f"frrk8s_bgp_session_up{SCOPED} and on() ega_path_probe_success"))

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
        self.assertEqual(self.check(dashboard)[0], "1 panels, 1 PromQL queries OK")

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


class GrafanaAlertsTest(unittest.TestCase):
    """Grafana alert rules must be consistent and match the dashboard panels they link to."""

    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        _, uid, by_id = check_dashboards.check_dashboard(os.path.join(root, "dashboards", "aws-transport.json"))
        self.dashboards = {uid: by_id}
        with open(os.path.join(root, "grafana", "aws-transport-alerts.yaml")) as f:
            self.rule = check_dashboards.yaml.safe_load(f)["groups"][0]["rules"][0]

    def broken(self, change):
        rule = copy.deepcopy(self.rule)
        change(rule)
        with self.assertRaises(ValueError) as error:
            check_dashboards.check_alert_rule(rule, self.dashboards)
        return str(error.exception)

    def test_shipped_rule_passes(self):
        check_dashboards.check_alert_rule(self.rule, self.dashboards)

    def test_missing_panel_fails(self):
        self.assertIn("no panel", self.broken(lambda r: r.update(panelId=99)))

    def test_bad_state_fails(self):
        self.assertIn("noDataState", self.broken(lambda r: r.update(noDataState="Bogus")))

    def test_reference_to_missing_query_fails(self):
        self.assertIn("not an earlier query", self.broken(lambda r: r["data"][1]["model"].update(expression="Z")))
        self.assertIn("not an earlier query", self.broken(lambda r: r["data"][2]["model"].update(expression="$Z < 1")))

    def test_query_that_differs_from_panel_fails(self):
        self.assertIn("differs", self.broken(lambda r: r["data"][0]["model"].update(metricName="ConnectonState")))

    def test_short_time_range_fails(self):
        self.assertIn("two", self.broken(lambda r: r["data"][0]["relativeTimeRange"].update({"from": 300})))

    def test_missing_key_fails(self):
        self.assertIn("no dashboardUid", self.broken(lambda r: r.pop("dashboardUid")))

    def test_bad_error_state_fails(self):
        self.assertIn("execErrState", self.broken(lambda r: r.update(execErrState="Bogus")))

    def test_statistic_period_or_dimension_mismatch_fails(self):
        self.assertIn("differs", self.broken(lambda r: r["data"][0]["model"].update(statistic="Maximum")))
        self.assertIn("differs", self.broken(lambda r: r["data"][0]["model"].update(period="60")))
        self.assertIn("differs", self.broken(lambda r: r["data"][0]["model"]["dimensions"].update(VpnId=["*"])))
        self.assertIn("differs", self.broken(lambda r: r["data"][0]["model"].update(matchExact=True)))

    def test_non_cloudwatch_query_fails(self):
        def change(rule):
            rule["data"][0]["model"] = {"refId": "A", "expr": "up"}
        self.assertIn("CloudWatch", self.broken(change))

    def test_unknown_condition_fails(self):
        self.assertIn("condition", self.broken(lambda r: r.update(condition="X")))

    def test_condition_on_raw_query_fails(self):
        self.assertIn("expression query", self.broken(lambda r: r.update(condition="A")))

    def test_non_numeric_period_fails(self):
        self.assertIn("period in seconds", self.broken(lambda r: r["data"][0]["model"].update(period="auto")))

    def test_file_without_groups_passes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
            f.write("apiVersion: 1\ncontactPoints: []\n")
            f.flush()
            self.assertEqual(check_dashboards.check_alerts(f.name, self.dashboards), "0 alert rules OK")


class CloudWatchDashboardTest(unittest.TestCase):
    def check_broken(self, change):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        with open(os.path.join(root, "dashboards", "aws-transport.json")) as f:
            dashboard = json.load(f)
        change(dashboard)
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(dashboard, f)
            f.flush()
            with self.assertRaises(ValueError) as error:
                check_dashboards.check_dashboard(f.name)
        return str(error.exception)

    def test_target_without_metric_fails(self):
        self.assertIn("no metricName", self.check_broken(lambda d: d["panels"][0]["targets"][0].pop("metricName")))

    def test_missing_datasource_variable_fails(self):
        def change(d):
            d["templating"]["list"] = [v for v in d["templating"]["list"] if v["name"] != "datasource"]
        self.assertIn("datasource variable", self.check_broken(change))

    def test_variable_on_other_datasource_fails(self):
        def change(d):
            d["templating"]["list"][-1]["datasource"] = {"type": "cloudwatch", "uid": "other"}
        self.assertIn("query variables", self.check_broken(change))


if __name__ == "__main__":
    unittest.main()
