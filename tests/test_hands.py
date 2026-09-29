import pytest
from cascadeur_mcp.bridge.protocol import validate_params, BridgeError

BASE={'scene_id':'a'*32,'character_id':'12345678-1234-1234-1234-123456789012'}

def test_valid_hand_sequence():
    p={**BASE,'poses':[{'frame':10,'hands':{'right':{'index1':[1,0,0,0]}}}]}
    assert validate_params('set_hand_pose_sequence',p)==p

@pytest.mark.parametrize('hands', [None,{}, {'other':{}}, {'right':{}},
    {'right':{'wrist':[1,0,0,0]}}, {'right':{'index4':[1,0,0,0]}},
    {'right':{'index1':[2,0,0,0]}}, {'right':{'index1':[True,0,0,0]}},
    {'right':{'index1':[float('nan'),0,0,0]}}, {'right':{'index1':[0,0,0,0]}}])
def test_reject_invalid_hand_shapes(hands):
    with pytest.raises(BridgeError):
        validate_params('set_hand_pose_sequence',{**BASE,'poses':[{'frame':10,'hands':hands}]})

def test_duplicate_frame_rejected():
    entry={'frame':10,'hands':{'right':{'index1':[1,0,0,0]}}}
    with pytest.raises(BridgeError):
        validate_params('set_hand_pose_sequence',{**BASE,'poses':[entry,entry]})
