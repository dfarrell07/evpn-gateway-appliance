"""Run Direct Connect task scenarios against the fake CLI. Usage (in the CI image): python3 run.py [scenario...]"""
import copy, json, os, subprocess, sys

T = os.path.dirname(os.path.abspath(__file__))
SECRET = 'TESTONLY-md5-authkey-do-not-print'
DXGW = '5f0e6c1e-1b1a-4c2a-9a55-0123456789ab'
BASE = {
    'vifs': [
        {'virtualInterfaceId': 'dxvif-aaaa1111', 'virtualInterfaceType': 'transit', 'virtualInterfaceState': 'available',
         'mtu': 8500, 'jumboFrameCapable': True, 'directConnectGatewayId': DXGW,
         'bgpPeers': [{'bgpStatus': 'up', 'authKey': SECRET}, {'bgpStatus': 'up', 'authKey': SECRET}]},
        # In another Region than the TGW (us-west-2): read there or it is not found.
        {'virtualInterfaceId': 'dxvif-bbbb2222', 'virtualInterfaceType': 'transit', 'virtualInterfaceState': 'available',
         'mtu': 8500, 'jumboFrameCapable': True, 'directConnectGatewayId': DXGW, 'region': 'us-east-1',
         'bgpPeers': [{'bgpStatus': 'up', 'bgpPeerState': 'available', 'authKey': SECRET},
                      {'bgpStatus': 'down', 'bgpPeerState': 'deleted', 'authKey': SECRET}]},
        {'virtualInterfaceId': 'dxvif-other999', 'virtualInterfaceType': 'private', 'virtualInterfaceState': 'down',
         'mtu': 1500, 'directConnectGatewayId': 'other', 'bgpPeers': [{'bgpStatus': 'down', 'authKey': SECRET}]},
    ],
    'assocs': [],
    'dxgws': [{'directConnectGatewayId': DXGW, 'directConnectGatewayState': 'available', 'amazonSideAsn': 64600}],
    'tgws': [{'TransitGatewayId': 'tgw-0001', 'State': 'available', 'Tags': [{'Key': 'Project', 'Value': 'stubproj'}],
              'Options': {'AssociationDefaultRouteTableId': 'tgw-rtb-0001'}}],
    'routes': {'tgw-rtb-0001': [{'DestinationCidrBlock': '10.44.44.0/24', 'State': 'active',
                                 'TransitGatewayAttachments': [{'ResourceType': 'direct-connect-gateway'}]}]},
}
MUTATING = ('create-direct-connect-gateway-association', 'delete-direct-connect-gateway-association')


def other_assoc(prefixes, tgw='tgw-elsewhere', state='associated'):
    return {'associationId': 'assoc-x%s' % tgw, 'directConnectGatewayId': DXGW,
            'associatedGateway': {'id': tgw, 'type': 'transitGateway'}, 'associationState': state,
            'allowedPrefixesToDirectConnectGateway': [{'cidr': p} for p in prefixes]}


def run(steps, state, extra=()):
    sf, log = os.path.join(T, 'state.json'), os.path.join(T, 'argv.log')
    json.dump(state, open(sf, 'w'))
    open(log, 'w').close()
    env = dict(os.environ, STUB_STATE=sf, STUB_ARGV_LOG=log, PATH=T + '/bin:' + os.environ['PATH'],
               ANSIBLE_NOCOLOR='1', ANSIBLE_LOCALHOST_WARNING='false', ANSIBLE_INVENTORY_UNPARSED_WARNING='false')
    cmd = ['ansible-playbook', '-v', T + '/plays/run.yml', '-e', 'steps=' + steps]
    for e in extra:
        cmd += ['-e', e]
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    calls = [json.loads(line) for line in open(log)]
    return p, calls, json.load(open(sf))


def mut(calls):
    return [c[1] for c in calls if c[1] in MUTATING]


results = []


def check(name, cond, detail=''):
    results.append((name, cond))
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '\n   ' + detail[-1500:]))


def leak(p):
    return SECRET in p.stdout or SECRET in p.stderr


def neg(name, steps, mutate, extra=(), want=''):
    s = copy.deepcopy(BASE)
    mutate(s)
    p, calls, _ = run(steps, s, extra)
    out = p.stdout + p.stderr
    check(name, p.returncode != 0 and not mut(calls) and not leak(p) and want in out, out)


def vif(s, i, **kw):
    s['vifs'][i].update(kw)


# Lifecycle: preflight, associate, status, rerun preflight blocked, teardown twice.
s = copy.deepcopy(BASE)
p, calls, st = run('dx_preflight,dx', s)
check('lifecycle: preflight and associate', p.returncode == 0 and mut(calls) == [MUTATING[0]] and not leak(p)
      and [a['associationState'] for a in st['assocs']] == ['associated'], p.stdout + p.stderr)
create = [c for c in calls if c[1] == MUTATING[0]][0]
check('lifecycle: association allows exactly the two VPC CIDRs',
      create[create.index('--add-allowed-prefixes-to-direct-connect-gateway') + 1:][:2] == ['cidr=10.100.0.0/16', 'cidr=10.200.0.0/16'],
      json.dumps(create))
p, calls, st2 = run('dx_status', st)
check('lifecycle: status passes', p.returncode == 0 and not mut(calls) and not leak(p), p.stdout + p.stderr)
p, calls, _ = run('dx_preflight', st)
check('lifecycle: rerun preflight blocks before changes', p.returncode != 0 and not mut(calls)
      and 'teardown-aws.yml' in p.stdout, p.stdout)
p, calls, st3 = run('teardown_dx', st)
check('lifecycle: teardown deletes only the project association', p.returncode == 0 and mut(calls) == [MUTATING[1]]
      and all(a['associationState'] == 'disassociated' for a in st3['assocs']), p.stdout + p.stderr)
p, calls, _ = run('teardown_dx', st3)
check('lifecycle: teardown again is a no-op', p.returncode == 0 and not mut(calls), p.stdout + p.stderr)
s = copy.deepcopy(BASE)
s['assocs'] = [other_assoc(['10.50.0.0/16'])]
p, calls, st4 = run('teardown_dx', s)
check('teardown leaves another TGW\'s association alone', p.returncode == 0 and not mut(calls)
      and st4['assocs'][0]['associationState'] == 'associated', p.stdout + p.stderr)

# Preflight negatives: each fails before any change and prints no MD5 key.
neg('preflight: private VIF', 'dx_preflight', lambda s: vif(s, 0, virtualInterfaceType='private'))
neg('preflight: VIF down', 'dx_preflight', lambda s: vif(s, 1, virtualInterfaceState='down'))
neg('preflight: one BGP peer down', 'dx_preflight', lambda s: s['vifs'][0]['bgpPeers'][1].update(bgpStatus='down'))
neg('preflight: no BGP peers', 'dx_preflight', lambda s: vif(s, 1, bgpPeers=[]))
neg('preflight: 1500 MTU in safe mode', 'dx_preflight', lambda s: vif(s, 0, mtu=1500))
neg('preflight: VIF on another DX gateway', 'dx_preflight', lambda s: vif(s, 1, directConnectGatewayId='other'))
neg('preflight: a private VIF also attached to the DX gateway', 'dx_preflight',
    lambda s: vif(s, 2, directConnectGatewayId=DXGW), want='PrivateVirtualInterface')
neg('preflight: VIF ID not found', 'dx_preflight', lambda s: s['vifs'].pop(1))
neg('preflight: malformed DX gateway ID', 'dx_preflight', lambda s: None, ['dxgw=dxgw-123'])
neg('preflight: no VIF IDs', 'dx_preflight', lambda s: None, ['{"vifs": []}'])
neg('preflight: duplicate VIF IDs', 'dx_preflight', lambda s: None, ['{"vifs": ["dxvif-aaaa1111", "dxvif-aaaa1111"]}'])
neg('preflight: DX gateway not found', 'dx_preflight', lambda s: s['dxgws'].clear())
neg('preflight: DX gateway deleting', 'dx_preflight', lambda s: s['dxgws'][0].update(directConnectGatewayState='deleting'))
neg('preflight: DX gateway ASN equals the TGW ASN', 'dx_preflight', lambda s: s['dxgws'][0].update(amazonSideAsn=64512),
    want='64512')
neg('preflight: DX gateway has six TGWs', 'dx_preflight',
    lambda s: s['assocs'].extend(other_assoc(['10.%d.0.0/16' % i], 'tgw-%d' % i) for i in range(6)), want='found 6')
neg('preflight: hosted VIF not yet accepted', 'dx_preflight', lambda s: vif(s, 1, virtualInterfaceState='confirming'))
def vgw(s):
    a = other_assoc([])
    a['associatedGateway'] = {'id': 'vgw-1', 'type': 'virtualPrivateGateway'}
    s['assocs'].append(a)
neg('preflight: DX gateway associated with a VGW', 'dx_preflight', vgw, want='virtualPrivateGateway')
neg('preflight: allowed prefix contains a VPC', 'dx_preflight', lambda s: s['assocs'].append(other_assoc(['10.0.0.0/8'])),
    want='10.0.0.0/8')
neg('preflight: allowed prefix inside a VPC', 'dx_preflight', lambda s: s['assocs'].append(other_assoc(['10.200.5.0/24'])),
    want='10.200.5.0/24')
s = copy.deepcopy(BASE)
vif(s, 0, mtu=1500)
p, calls, _ = run('dx_preflight', s, ['mtu_mode=unsafe'])
check('preflight: 1500 MTU passes in unsafe mode', p.returncode == 0 and not mut(calls), p.stdout + p.stderr)
s = copy.deepcopy(BASE)
s['assocs'] = [other_assoc(['10.50.0.0/16']), other_assoc(['10.200.0.0/16'], 'tgw-gone', 'disassociated')]
p, calls, _ = run('dx_preflight', s)
check('preflight: ignores disassociated and non-overlapping associations', p.returncode == 0, p.stdout + p.stderr)

# Status negatives (before deploy and in health checks).
s = copy.deepcopy(BASE)
s['assocs'] = [other_assoc(['10.100.0.0/16'], 'tgw-0001')]
neg('status: association misses the workload VPC', 'dx_status', lambda x: x.update(copy.deepcopy(s)), want="uncovered: ['10.200.0.0/16']")
neg('status: no association', 'dx_status', lambda x: None, want="uncovered: ['10.100.0.0/16', '10.200.0.0/16']")
s2 = copy.deepcopy(BASE)
s2['assocs'] = [other_assoc(['10.100.0.0/16', '10.200.0.0/16'], 'tgw-0001')]
s2['routes']['tgw-rtb-0001'] = [{'DestinationCidrBlock': '10.44.0.0/16', 'State': 'active',
                                 'TransitGatewayAttachments': [{'ResourceType': 'direct-connect-gateway'}]},
                                {'DestinationCidrBlock': '10.0.0.0/8', 'State': 'active',
                                 'TransitGatewayAttachments': [{'ResourceType': 'vpc'}]}]
p, calls, _ = run('dx_status', s2)
check('status: a covering DX aggregate passes', p.returncode == 0 and not mut(calls) and not leak(p), p.stdout + p.stderr)
if '--slow' in sys.argv:
    neg('status: a more specific non-DX route wins (slow)', 'dx_status',
        lambda x: (x.update(copy.deepcopy(s2)), x['routes']['tgw-rtb-0001'].append(
            {'DestinationCidrBlock': '10.44.44.0/24', 'State': 'active', 'TransitGatewayAttachments': [{'ResourceType': 'vpc'}]})))
    neg('status: VIF BGP down (slow)', 'dx_status',
        lambda x: (x.update(copy.deepcopy(s2)), x['vifs'][0]['bgpPeers'][0].update(bgpStatus='down')))
    s['assocs'] = [other_assoc(['10.100.0.0/16', '10.200.0.0/16'], 'tgw-0001')]
    s['routes']['tgw-rtb-0001'][0]['TransitGatewayAttachments'] = [{'ResourceType': 'vpc'}]
    neg('status: TGW route not via DX (slow, 30 retries)', 'dx_status', lambda x: x.update(copy.deepcopy(s)),
        want='direct-connect-gateway')

failed = [n for n, ok in results if not ok]
print('%d passed, %d failed' % (len(results) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
