#!/usr/bin/python
# Fake k8s_info for test/discovery/run.sh: returns FAKE_PODS ("node=hostIP ..." pairs) as
# Running frr-k8s pods, or fails like an unreachable API when FAKE_PODS is "unreachable". It
# also fails on any other query, or when it runs on the relay (whose remote_tmp names it).
import os

from ansible.module_utils.basic import AnsibleModule


def main():
    args = ("api_version", "kind", "namespace", "label_selectors", "field_selectors")
    module = AnsibleModule(argument_spec={a: {"type": "raw"} for a in args}, supports_check_mode=True)
    query = [module.params[a] for a in args[2:]]
    if query != ["openshift-frr-k8s", ["app=frr-k8s"], ["status.phase=Running"]] or "relay" in module._remote_tmp:
        module.fail_json(msg="fake: unexpected query %s from %s" % (query, module._remote_tmp))
    pods = os.environ.get("FAKE_PODS", "")
    if pods == "unreachable":
        module.fail_json(msg="fake API unreachable")
    resources = []
    for pair in pods.split():
        node, ip = pair.split("=")
        resources.append({"spec": {"nodeName": node}, "status": {"phase": "Running", "hostIP": ip}})
    module.exit_json(changed=False, resources=resources)


if __name__ == "__main__":
    main()
