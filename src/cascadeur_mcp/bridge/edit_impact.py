"""Summarize verified native Point evidence; never write or read the scene."""
import math
from .protocol import BridgeError

REPORTING_THRESHOLD = .001  # display grouping only; not a solver/safety tolerance


def _vector(item):
    value = item['position']
    if (not isinstance(value, list) or len(value) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('invalid native Point position')
    return value


def build(rig, before, entries, actual_poses, *, selected_roles):
    """Use pre-edit targets and verified solved poses inside transaction checks.

    The post-commit check replaces the earlier report. Incomplete evidence
    rejects the transaction. Joint rotation and trajectories are not compared.
    """
    try:
        frames = [entry['frame'] for entry in entries]
        if (not 1 <= len(frames) <= 8 or len(set(frames)) != len(frames)
                or [pose['frame'] for pose in actual_poses] != frames
                or not selected_roles or set(selected_roles) - rig['roles'].keys()):
            raise ValueError('inconsistent frame or role evidence')
        selected = [role for role in rig['roles'] if role in selected_roles]
        result_frames = []
        for entry, actual in zip(entries, actual_poses):
            frame = entry['frame']
            direct, coupled, small = {}, {}, []
            max_small = max_unselected = 0.
            for role, group in rig['roles'].items():
                slots = {}
                role_max = 0.
                written = role in selected
                for slot, control in group['controls'].items():
                    oid = control['control_id']
                    old = _vector(before[frame][oid])
                    target = _vector(entry['pose'][oid])
                    solved = _vector(actual['pose'][oid])
                    delta = [new - prior for new, prior in zip(solved, old)]
                    displacement = math.hypot(*delta)
                    target_error = math.dist(solved, target)
                    if not math.isfinite(displacement) or not math.isfinite(target_error):
                        raise ValueError('nonfinite derived evidence')
                    role_max = max(role_max, displacement)
                    slots[slot] = {'control_id': oid, 'directly_written': written,
                                   'actual_delta': delta, 'displacement': displacement,
                                   'target_error': target_error}
                detail = {'slots': slots, 'max_displacement': role_max}
                if written:
                    direct[role] = detail
                else:
                    max_unselected = max(max_unselected, role_max)
                    if role_max > REPORTING_THRESHOLD:
                        coupled[role] = detail
                    else:
                        small.append(role)
                        max_small = max(max_small, role_max)
            result_frames.append({'frame': frame, 'direct_roles': direct,
                                  'coupled_roles': coupled,
                                  'below_threshold_roles': small,
                                  'max_below_threshold_displacement': max_small,
                                  'max_unselected_displacement': max_unselected})
        return {'schema_version': 1,
                'basis': 'pre-edit targets versus verified post-commit native Point targets',
                'coordinate_space': 'world positions in native scene units',
                'distance_metric': 'Euclidean',
                'reporting_threshold': REPORTING_THRESHOLD,
                'threshold_purpose': 'response grouping only; no safety tolerance is changed',
                'selected_roles': selected,
                'direct_point_writes': len(frames) * sum(len(rig['roles'][r]['controls']) for r in selected),
                'frames': result_frames,
                'scope': 'Point targets at requested frames only; below-threshold is not unchanged; Joint state, trajectory and visual quality are not measured'}
    except Exception as exc:
        raise BridgeError('EDIT_IMPACT_UNAVAILABLE: native reporting evidence is incomplete or nonfinite') from exc
