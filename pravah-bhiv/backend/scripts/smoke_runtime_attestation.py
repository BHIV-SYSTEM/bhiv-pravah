import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from contracts.runtime_attestation import compute_runtime_attestation
from contracts.policy_snapshot import compute_policy_hash
from control_plane.core.action_governance import ActionGovernance
from contracts.decision_contract import validate_decision_contract
from contracts.execution_contract import build_execution_contract
from control_plane.core.execution_lineage import replay_execution_lineage

# compute attestation
att = compute_runtime_attestation()
print('attestation:', att.model_dump())

# policy snapshot
g = ActionGovernance(env='dev')
policy_hash = compute_policy_hash(g.get_config())
policy_snapshot = {'policy_id': g.POLICY_ID, 'policy_version': 'v1', 'policy_hash': policy_hash}

# build contract
decision = validate_decision_contract({'decision_type':'execution','action':'restart','parameters':{'service_id':'svc'},'version':'v1'})
contract = build_execution_contract(decision, {'service_id':'svc'}, approved_by='tester', policy_snapshot=policy_snapshot, runtime_attestation=att.model_dump())
print('contract.execution_hash:', contract.execution_hash)

# replay
r = replay_execution_lineage(contract.execution_id)
print('replay contains runtime_attestation in approved event:', any(e.get('details',{}).get('runtime_attestation') for e in r['events']))
if len(r.get('events'))>1:
    print('replay runtime_attestation:', r.get('events')[1].get('details').get('runtime_attestation'))
else:
    print('no events')
