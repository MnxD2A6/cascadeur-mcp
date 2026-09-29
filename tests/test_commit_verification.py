"""Regression for native layer edits finalized after modify_update callbacks."""
import copy
import pytest
from cascadeur_mcp.bridge import character
from cascadeur_mcp.bridge.protocol import BridgeError

def test_verify_uses_committed_tracks_not_callback_snapshot(monkeypatch):
    before={'tracks':{'arm':{'interpolation':2}}}
    committed={'tracks':{'arm':{'interpolation':3}}}
    monkeypatch.setattr(character,'capture',lambda scene:copy.deepcopy(committed))
    def verify():
        assert character.capture(None)['tracks']['arm']['interpolation']==3
        return character.capture(None)
    actual=character._verify_committed(None,{'state':before},verify,before)
    assert actual==committed and actual!=before

def test_postcommit_validation_failure_restores_recorded_prestate(monkeypatch):
    before={'tracks':{'arm':{'interpolation':2}}}
    committed={'tracks':{'arm':{'interpolation':3}}}
    observed=[]
    monkeypatch.setattr(character,'capture',lambda scene:copy.deepcopy(committed))
    def undo(scene,snapshot,known):
        observed.append(known)
        assert known[-1]==committed and snapshot['state']==before
    monkeypatch.setattr(character,'restore_native',undo)
    def fail():raise BridgeError('POSTCONDITION_FAILED')
    with pytest.raises(BridgeError,match='POSTCONDITION_FAILED'):
        character._verify_committed(None,{'state':before},fail,before)
    assert len(observed)==1

def test_restore_still_rejects_external_track_edit(monkeypatch):
    scene=object();before={'tracks':2};after={'tracks':3};current={'tracks':4}
    monkeypatch.setattr(character,'_snapshots',{'snapshot':{'scene':scene,'scene_id':'scene',
        'lineage':[],'state':before}})
    monkeypatch.setattr(character,'scene_id',lambda v:'scene')
    monkeypatch.setattr(character,'journal',lambda s:{'entries':[{'id':'one','before':before,'after':after}]})
    monkeypatch.setattr(character,'capture',lambda s:current)
    def forbidden(*args):pytest.fail('Must not undo external edits')
    monkeypatch.setattr(character,'restore_native',forbidden)
    with pytest.raises(BridgeError,match='EXTERNAL_EDIT_DETECTED'):
        character.restore(None,scene,'snapshot')
