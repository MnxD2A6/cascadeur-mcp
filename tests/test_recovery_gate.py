"""Offline dispatch regression; native fault-injection acceptance is separate."""
from types import SimpleNamespace as NS

import pytest

from cascadeur_mcp.bridge import animation, character, playback, polish
from cascadeur_mcp.bridge.protocol import BridgeError
from cascadeur_mcp.tools.animation_schema import WRITE_METHODS


def frame_scene():
    state = {'frame': 0}
    scene = NS(get_current_frame=lambda: state['frame'],
               set_current_frame=lambda frame: state.update(frame=frame),
               model_viewer=lambda: NS(data_viewer=lambda: NS(get_animation_size=lambda: 23)))
    return scene, state


def lock(monkeypatch, scene):
    entry = {'scene': scene, 'entries': [], 'locked': True}
    monkeypatch.setattr(character, '_journals', {id(scene): entry})
    return entry


def test_legacy_frame_write_cannot_bypass_failed_character_recovery(monkeypatch):
    scene, state = frame_scene()
    lock(monkeypatch, scene)
    with pytest.raises(BridgeError, match='RECOVERY_REQUIRED') as failure:
        animation.dispatch(NS(name=lambda: 'test.casc'), scene, 'set_current_frame',
                           {'scene': 'test.casc', 'frame': 10})
    assert failure.value.execution_state == 'recovery_required'
    assert failure.value.rollback_verified is False
    assert state['frame'] == 0


class NoNativeAccess:
    def __getattr__(self, name):
        pytest.fail(f'Locked scene reached native/adapter access: {name}')


@pytest.mark.parametrize('method', sorted(WRITE_METHODS - {'stop_animation', 'save_scene_copy'}))
def test_every_write_route_checks_lock_before_adapter_access(monkeypatch, method):
    scene = NoNativeAccess()
    entry = lock(monkeypatch, scene)
    # Exercise dispatch boundary; schema validation belongs to the caller.
    # No adapter-specific arguments should be read for an already locked scene.
    with pytest.raises(BridgeError, match='RECOVERY_REQUIRED') as failure:
        animation.dispatch(NoNativeAccess(), scene, method, {})
    assert failure.value.execution_state == 'recovery_required'
    assert failure.value.rollback_verified is False
    assert character._journals == {id(scene): entry}
    assert entry['locked'] is True


@pytest.mark.parametrize('method,adapter', [('stop_animation', playback), ('save_scene_copy', polish)])
def test_locked_scene_can_stop_or_save_quarantine_without_unlocking(monkeypatch, method, adapter):
    scene = NoNativeAccess()
    entry = lock(monkeypatch, scene)
    called = []
    def dispatch(view, actual_scene, actual_method, params):
        called.append((actual_scene, actual_method, params))
        return {'allowed': True}
    monkeypatch.setattr(adapter, 'dispatch', dispatch)
    assert animation.dispatch(None, scene, method, {'sentinel': True}) == {'allowed': True}
    assert called == [(scene, method, {'sentinel': True})]
    assert entry['locked'] is True


def test_readback_remains_available_on_locked_scene(monkeypatch):
    scene, state = frame_scene()
    entry = lock(monkeypatch, scene)
    assert animation.dispatch(NS(name=lambda: 'test.casc'), scene, 'get_current_frame', {})['current_frame'] == 0
    assert entry['locked'] and state['frame'] == 0


@pytest.mark.parametrize('other_scene_locked', [False, True])
def test_untracked_scene_is_not_locked_or_added_to_character_cache(monkeypatch, other_scene_locked):
    scene, state = frame_scene()
    other = object()
    entries = {id(other): {'scene': other, 'entries': [], 'locked': True}} if other_scene_locked else {}
    monkeypatch.setattr(character, '_journals', entries.copy())
    result = animation.dispatch(NS(name=lambda: 'test.casc'), scene, 'set_current_frame',
                                {'scene': 'test.casc', 'frame': 10})
    assert result['current_frame'] == state['frame'] == 10
    assert character._journals == entries
