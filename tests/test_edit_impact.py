"""Pure reporting regressions, not a replacement for native acceptance."""
import copy
import pytest
from cascadeur_mcp.bridge import semantics
from cascadeur_mcp.bridge.protocol import BridgeError


def data():
    rig = {'roles': {
        'right_hand': {'controls': {'center': {'control_id': 'hand'}}},
        'right_elbow': {'controls': {'bend': {'control_id': 'elbow'}}},
        'left_foot': {'controls': {'center': {'control_id': 'foot'}}},
    }}
    before = {10: {'hand': {'position': [10., 0., 0.]},
                   'elbow': {'position': [20., 0., 0.]},
                   'foot': {'position': [0., 0., 0.]}}}
    requested = [{'frame': 10, 'pose': copy.deepcopy(before[10])}]
    requested[0]['pose']['hand']['position'] = [12., 0., 0.]
    actual = [{'frame': 10, 'pose': {
        'hand': {'position': [11.5, 0., 0.]},
        'elbow': {'position': [20., .2, 0.]},
        'foot': {'position': [.0001, 0., 0.]},
    }}]
    return rig, before, requested, actual


def build(args):
    return semantics.build_edit_impact(*args, selected_roles=['right_hand'])


def test_actual_displacement_is_not_solver_error_against_requested_target():
    report = build(data())
    hand = report['frames'][0]['direct_roles']['right_hand']['slots']['center']
    assert hand['actual_delta'] == [1.5, 0., 0.]
    assert hand['displacement'] == 1.5
    assert hand['target_error'] == .5
    assert hand['directly_written'] is True
    assert report['direct_point_writes'] == 1


def test_unselected_coupled_role_is_named_and_small_changes_are_not_called_unchanged():
    report = build(data())
    frame = report['frames'][0]
    elbow = frame['coupled_roles']['right_elbow']['slots']['bend']
    assert elbow['actual_delta'] == [0., .2, 0.]
    assert elbow['displacement'] == pytest.approx(.2)
    assert elbow['directly_written'] is False
    assert frame['below_threshold_roles'] == ['left_foot']
    assert frame['max_below_threshold_displacement'] == .0001
    assert report['reporting_threshold'] == .001


def test_distance_metric_uses_all_axes_and_preserves_inputs():
    args = data()
    args[3][0]['pose']['hand']['position'] = [13., 4., 0.]
    preserved = copy.deepcopy(args)
    report = build(args)
    assert report['frames'][0]['direct_roles']['right_hand']['slots']['center']['displacement'] == 5.
    assert args == preserved


def test_each_frame_uses_its_own_baseline_in_request_order():
    rig, before, requested, actual = data()
    before[6] = copy.deepcopy(before[10])
    before[6]['hand']['position'] = [100., 0., 0.]
    requested.append({'frame': 6, 'pose': copy.deepcopy(before[6])})
    actual.append({'frame': 6, 'pose': copy.deepcopy(before[6])})
    actual[1]['pose']['hand']['position'] = [101., 0., 0.]
    report = build((rig, before, requested, actual))
    assert [item['frame'] for item in report['frames']] == [10, 6]
    assert report['frames'][1]['direct_roles']['right_hand']['slots']['center']['actual_delta'] == [1., 0., 0.]
    assert report['direct_point_writes'] == 2


@pytest.mark.parametrize('fault', ['missing_control', 'nonfinite', 'bool', 'wrong_frame', 'duplicate_frame'])
def test_incomplete_or_nonfinite_native_evidence_fails_instead_of_reporting_success(fault):
    args = data()
    if fault == 'missing_control': del args[3][0]['pose']['elbow']
    elif fault == 'nonfinite': args[3][0]['pose']['hand']['position'][0] = float('nan')
    elif fault == 'bool': args[3][0]['pose']['hand']['position'][0] = True
    elif fault == 'wrong_frame': args[3][0]['frame'] = 9
    elif fault == 'duplicate_frame': args[3].append(copy.deepcopy(args[3][0]))
    with pytest.raises(BridgeError, match='EDIT_IMPACT_UNAVAILABLE'):
        build(args)
