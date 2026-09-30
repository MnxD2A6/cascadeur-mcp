# Semantic edit-impact reports

Version `0.5.0a7` adds `edit_impact` to successful
`offset_semantic_pose_sequence_preserving_curves` results. No new MCP tool or
input option is required. Existing offset arguments and limits still apply.
Ordinary key-authoring tools do not produce this report.

Discover support in the responding host's
`write_features.offset_semantic_pose_sequence_preserving_curves.edit_impact`.
An older compatible host may accept the same write but omit this optional result.
Package labels and matching write contracts are not report-feature discovery.
Restart host and server after updating source; hot reload remains unsupported.

## How to read the result

Each `frames` entry contains:

- `direct_roles`: selected semantic groups; every slot was directly written.
- `coupled_roles`: unselected groups whose actual Point displacement exceeds
  the reporting threshold. They can move through the native rig solver.
- `below_threshold_roles`: other groups below the threshold, not proof of zero
  movement. `max_below_threshold_displacement` retains their largest difference.
- `max_unselected_displacement`: the largest movement among all unselected roles.

Detailed slots retain discovered `control_id`, `directly_written`, `actual_delta`,
`displacement` and `target_error`. Actual delta compares solved targets to that
frame's own pre-edit targets. Target error compares solved targets to requested
absolute targets. These are different measurements.

Distances are Euclidean in native world scene units. Existing
`max_target_adjustment` uses maximum component error; its number is not the same
metric. Neither measure is centimeters, a Token count or a motion-quality score.

The 0.001-unit threshold only groups the response. It does not relax validation,
change rig solving or hide the maximum difference among small changes. Selected
groups are always detailed even if their displacement is zero.

`protection` contains the existing completed curve-guard evidence. Its verified
metadata, baked/external/settings protection and whole-clip anchor checks retain
the original exactness/tolerances and scope. It does not promise a fixed edited
trajectory or bit-exact Point positions.

## Transaction and scope

The report uses pre-edit Point targets already read for the offset and native
poses already collected by transaction verification. No report-only native read
or extra MCP round trip is introduced. Post-commit verification replaces the
earlier report. Incomplete/nonfinite reporting evidence fails within the existing
checked recovery boundary. Inspect error execution and rollback evidence.

The report covers Point targets at requested frames, not driven Joint rotations,
every inbetween trajectory, visual quality or automatic repair recommendations.
Existing `solver_adjustments` remains unchanged for older consumers.
