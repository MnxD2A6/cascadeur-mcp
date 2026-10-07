"""Disk/restart contracts; real host acceptance is a separate private harness."""
import copy
import hashlib
import json

import pytest
from cascadeur_mcp.bridge import character, recovery
from cascadeur_mcp.bridge.protocol import BridgeError, validate_params

@pytest.fixture
def checkpoint():
    return {'count':2,'objects':{'joint':{'parent':'root'}},
            'values':{'d:point':[[1.0,2.0,3.0],[2.0,3.0,4.0]]},
            'static':{'constraint':True},'tracks':{'arm':{'locked':False,'keys':[0,1]}}}

def seed(root, checkpoint):
    with recovery.host_context(root,'a'*32): recovery.persist(checkpoint)

def test_recovery_record_survives_restart_and_unsafe_scene_is_blocked(tmp_path,checkpoint,monkeypatch):
    seed(tmp_path,checkpoint)
    unsafe=copy.deepcopy(checkpoint);unsafe['values']['d:point'][1][0]+=1
    monkeypatch.setattr(character,'capture',lambda s:unsafe)
    with recovery.host_context(tmp_path,'b'*32):
        assert recovery.status(None)['status']=='CHECKPOINT_MISMATCH'
        with pytest.raises(BridgeError,match='RECOVERY_REQUIRED'):
            recovery.require_recovered(None)
    assert recovery.read(tmp_path)['checkpoint']==checkpoint

def test_matching_checkpoint_read_keeps_fence_successful_write_acknowledges_it(tmp_path,checkpoint,monkeypatch):
    seed(tmp_path,checkpoint);monkeypatch.setattr(character,'capture',lambda s:copy.deepcopy(checkpoint))
    path=tmp_path/'recovery-required.json';raw=path.read_bytes()
    with recovery.host_context(tmp_path,'b'*32):
        assert recovery.status(None)['status']=='VERIFIED_CHECKPOINT_READY'
        assert path.read_bytes()==raw
        recovery.require_recovered(None)
        assert path.exists()
        recovery.complete_write()
    assert not path.exists()

def test_same_session_cannot_unlock_even_if_state_matches(tmp_path,checkpoint,monkeypatch):
    seed(tmp_path,checkpoint);monkeypatch.setattr(character,'capture',lambda s:checkpoint)
    with recovery.host_context(tmp_path,'a'*32):
        assert recovery.status(None)['writes_blocked']
        with pytest.raises(BridgeError): recovery.require_recovered(None)

@pytest.mark.parametrize('damage',['truncate','checksum','nonfinite','oversize'])
def test_invalid_guard_fails_closed(tmp_path,checkpoint,monkeypatch,damage):
    seed(tmp_path,checkpoint);path=tmp_path/'recovery-required.json'
    if damage=='truncate':path.write_text('{')
    elif damage=='oversize':monkeypatch.setattr(recovery,'MAX_BYTES',10)
    else:
        item=json.loads(path.read_text())
        if damage=='checksum':item['checkpoint']['count']=3
        else:item['checkpoint']['values']['d:point'][0][0]=float('nan')
        path.write_text(json.dumps(item))
    with recovery.host_context(tmp_path,'b'*32):
        assert recovery.status(None)['status']=='INVALID_RECOVERY_RECORD'
        with pytest.raises(BridgeError): recovery.require_recovered(None)

@pytest.mark.parametrize('field',['static','tracks','objects'])
def test_unchanged_pose_does_not_hide_changed_constraints_or_structure(tmp_path,checkpoint,monkeypatch,field):
    seed(tmp_path,checkpoint);changed=copy.deepcopy(checkpoint);changed[field]['extra']=True
    monkeypatch.setattr(character,'capture',lambda s:changed)
    with recovery.host_context(tmp_path,'b'*32):
        assert recovery.status(None)['status']=='CHECKPOINT_MISMATCH'

def test_new_failure_cannot_be_deleted_by_old_verified_ticket(tmp_path,checkpoint,monkeypatch):
    seed(tmp_path,checkpoint);monkeypatch.setattr(character,'capture',lambda s:checkpoint)
    with recovery.host_context(tmp_path,'b'*32):
        recovery.require_recovered(None)
        recovery.persist(checkpoint)
        recovery.complete_write()
        assert recovery.read(tmp_path)['host_session']=='b'*32

def test_transport_envelope_limits_are_not_checkpoint_limits(tmp_path,checkpoint,monkeypatch):
    checkpoint['objects']['joint']['name']='x'*270000
    seed(tmp_path,checkpoint)
    assert recovery.read(tmp_path)['checkpoint']==checkpoint

def test_offline_adapter_does_not_touch_real_runtime(checkpoint):
    assert recovery._active is None
    recovery.persist(checkpoint)
    recovery.require_recovered(None)

def test_status_tool_rejects_external_arguments():
    assert validate_params('get_recovery_status',{})=={}
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params('get_recovery_status',{'unlock':True})

def test_doctor_reports_persistent_fence_without_exposing_model(tmp_path,checkpoint,monkeypatch):
    from cascadeur_mcp import manage
    seed(tmp_path,checkpoint)
    monkeypatch.setattr(manage,'instance_root',lambda i:tmp_path)
    monkeypatch.setattr(manage,'check_session',lambda *a,**k:{'ok':True,'status':'DESCRIPTOR_VALID_NOT_CONNECTED'})
    result=manage.doctor()
    assert result['status']=='ACTION_REQUIRED'
    assert result['recovery']['status']=='FENCE_PRESENT_NATIVE_CHECK_REQUIRED'
    assert 'd:point' not in json.dumps(result)
    assert recovery.read(tmp_path) is not None
