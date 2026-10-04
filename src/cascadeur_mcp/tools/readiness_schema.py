"""Read-only eligibility for existing semantic Point write operations."""
from .character_schema import SCENE, UUID, schema
from .semantic_schema import FRAMES, SELECTION, validate as validate_semantic

OPERATIONS = ('set_pose_sequence', 'offset_semantic_pose_sequence',
              'offset_semantic_pose_sequence_preserving_curves')
METHOD = 'get_character_edit_readiness'
SCHEMAS = {METHOD: schema({'scene_id': SCENE, 'character_id': UUID,
    'frames': FRAMES, 'operation': {'type': 'string', 'enum': list(OPERATIONS)},
    'roles': SELECTION['roles']}, ('scene_id', 'character_id', 'frames', 'operation', 'roles'))}
DESCRIPTIONS = {METHOD: 'Read current scene/rig/track eligibility and remaining character snapshot/transaction capacity for a specified semantic Point write. No snapshot, key, Undo, save or playhead change. PREFLIGHT_PASSED is advisory: target feasibility, external playback and native write success are not evaluated. Actual writes always recheck; never retry automatically. Capacity limits remain enforced; recover whole clips from separately saved native .casc checkpoints.'}

def validate(params):
    if type(params['operation']) is not str or params['operation'] not in OPERATIONS:
        raise ValueError('operation must name a supported semantic Point write')
    validate_semantic(METHOD, {k: v for k, v in params.items() if k != 'operation'})
