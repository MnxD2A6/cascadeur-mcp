"""Phase 2 validation/regression tests. Fakes here are not host acceptance."""
import asyncio
import sys
from types import SimpleNamespace as NS

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from cascadeur_mcp.bridge import animation, host
from cascadeur_mcp.bridge.client import BridgeClient
from cascadeur_mcp.bridge.protocol import BridgeError, validate_params
from cascadeur_mcp.tools.animation_schema import SCHEMAS, WRITE_METHODS

BASE = {'scene': 'test.casc', 'object': 'joint', 'frame': 10}


@pytest.mark.parametrize('method,params', [
    ('get_current_frame', {'frame': 0}),
    ('set_current_frame', {'scene': 'test.casc', 'frame': True}),
    ('set_current_frame', {'scene': 'test.casc', 'frame': -1}),
    ('set_current_frame', {'scene': 'test.casc', 'frame': 10001}),
    ('set_current_frame', {'frame': 0}),
    ('get_transform', {'object': ''}),
    ('get_transform', {'object': 'x\ncode'}),
    ('get_transform', {'object': 'x'*201}),
    ('set_transform', BASE),
    ('set_transform', {**BASE, 'position': [0, 1]}),
    ('set_transform', {**BASE, 'position': [True, 0, 0]}),
    ('set_transform', {**BASE, 'position': [float('nan'), 0, 0]}),
    ('set_transform', {**BASE, 'position': [float('inf'), 0, 0]}),
    ('set_transform', {**BASE, 'position': [1000001, 0, 0]}),
    ('set_transform', {**BASE, 'rotation_wxyz': [0, 0, 0, 0]}),
    ('set_transform', {**BASE, 'rotation_wxyz': [2, 0, 0, 0]}),
    ('set_transform', {**BASE, 'position': [0, 0, 0], 'code': 'anything'}),
    ('set_keyframe', {**BASE, 'path': '../outside'}),
    ('get_pose', {'frame': 0, 'objects': []}),
    ('get_pose', {'frame': 0, 'objects': ['same', 'same']}),
    ('get_pose', {'frame': 0, 'objects': ['x']*33}),
    ('get_pose', {'frame': 0, 'objects': [{}]}),
])
def test_bad_animation_input_rejected(method, params):
    with pytest.raises(BridgeError, match='INVALID_PARAMS'):
        validate_params(method, params)


def test_write_timeout_is_unknown_not_safe_failure(tmp_path):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    with pytest.raises(BridgeError, match='WRITE_OUTCOME_UNKNOWN'):
        BridgeClient(tmp_path, timeout=0.05).call('set_keyframe', BASE)


def test_scene_mismatch_prevents_all_host_access():
    with pytest.raises(BridgeError, match='SCENE_MISMATCH'):
        animation.dispatch(NS(name=lambda: 'other.casc'), object(), 'set_transform', BASE)


@pytest.mark.parametrize('frame', [1, 10])
def test_scene_frame_range_checked_before_mutation(frame):
    scene = NS(model_viewer=lambda: NS(data_viewer=lambda: NS(get_animation_size=lambda: 1)))
    with pytest.raises(BridgeError, match='FRAME_OUT_OF_RANGE'):
        animation.check_frame(scene, frame)


@pytest.mark.parametrize('locked,objects,error', [(True, {'joint'}, 'LOCKED_TRACK'),
                                                (False, {'joint', 'other'}, 'SHARED_TRACK')])
def test_unsafe_tracks_refused(locked, objects, error):
    layer = NS(is_locked=locked, obj_ids=objects)
    lv = NS(layer_id_by_obj_id=lambda obj: NS(is_null=lambda: False), layer=lambda lid: layer)
    with pytest.raises(BridgeError, match=error):
        animation.track(NS(layers_viewer=lambda: lv), 'joint', writable=True)


def test_nonkey_write_refused_before_csc_import(monkeypatch):
    monkeypatch.setattr(animation, 'check_frame', lambda *args: None)
    monkeypatch.setattr(animation, 'resolve', lambda *args: ('joint', {}))
    monkeypatch.setattr(animation, 'track', lambda *args, **kw: ('layer', object()))
    monkeypatch.setattr(animation, 'read_transform', lambda *args: {'is_key': False})
    with pytest.raises(BridgeError, match='KEY_REQUIRED'):
        animation.dispatch(NS(name=lambda: 'test.casc'), NS(get_current_frame=lambda: 0),
                           'set_transform', {**BASE, 'position': [1, 0, 0]})


def test_failed_modify_is_not_success(monkeypatch):
    monkeypatch.setattr(animation, 'check_frame', lambda *args: None)
    monkeypatch.setattr(animation, 'resolve', lambda *args: ('joint', {}))
    monkeypatch.setattr(animation, 'track', lambda *args, **kw: ('layer', object()))
    monkeypatch.setattr(animation, 'read_transform', lambda *args: {'is_key': False})
    scene = NS(get_current_frame=lambda: 0, modify=lambda *args: False)
    with pytest.raises(BridgeError, match='MODIFY_FAILED'):
        animation.dispatch(NS(name=lambda: 'test.casc'), scene, 'set_keyframe', BASE)


def test_readback_quaternion_sign_and_mismatch():
    animation.check_readback({'rotation_wxyz': [-1, 0, 0, 0]}, {'rotation_wxyz': [1, 0, 0, 0]})
    with pytest.raises(BridgeError, match='READBACK_MISMATCH'):
        animation.check_readback({'position': [0, 0, 0]}, {'position': [1, 0, 0]})
    with pytest.raises(BridgeError, match='READBACK_MISMATCH'):
        animation.check_readback({'rotation_wxyz': [0, 1, 0, 0]}, {'rotation_wxyz': [1, 0, 0, 0]})


def test_phase2_real_stdio_metadata_and_invalid_write(tmp_path):
    async def run():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'cascadeur_mcp.server'],
                                       env={'LOCALAPPDATA': str(tmp_path)})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                tools = {t.name: t for t in (await session.list_tools()).tools}
                assert set(SCHEMAS) <= set(tools)
                for name in SCHEMAS:
                    assert tools[name].annotations.readOnlyHint == (name not in WRITE_METHODS)
                for args in [{**BASE, 'rotation_wxyz': [0,0,0,0]}, {**BASE, 'position': [True,0,0]}, BASE]:
                    result = await session.call_tool('set_transform', args)
                    assert result.isError
                    assert 'BRIDGE_UNAVAILABLE' not in result.content[0].text
    asyncio.run(run())
