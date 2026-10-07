import unittest,json,sys
from pathlib import Path

from cascadeur_mcp.bridge.protocol import validate_params,MAX_BYTES,BridgeError
class SampledContract(unittest.TestCase):
 def setUp(self):
  from cascadeur_mcp.tools.semantic_schema import SLOTS
  self.poses=[{'frame':f,'pose':{r:{slot:[ri*20+si+f*.01,100+ri,0.0] for si,slot in enumerate(slots)} for ri,(r,slots) in enumerate(SLOTS.items())}} for f in range(64)]
  self.p={'scene_id':'a'*32,'character_id':'11111111-1111-1111-1111-111111111111','poses':self.poses,'sampled_motion':True}
 def test_complete_64_frame_sampled_motion_fits_unchanged_wire_budget(self):
  try:validated=validate_params('set_pose_sequence',self.p)
  except BridgeError as e:self.fail('Missing sampled-motion contract: '+str(e))
  self.assertEqual(len(validated['poses']),64)
  self.assertLess(len(json.dumps({'method':'set_pose_sequence','params':validated,'token':'a'*64,'session':'a'*32,'request_id':'a'*32}).encode()),MAX_BYTES)
 def test_normal_mode_still_rejects_more_than_eight(self):
  p=dict(self.p);p.pop('sampled_motion')
  with self.assertRaises(BridgeError):validate_params('set_pose_sequence',p)
 def test_duplicate_out_of_order_and_incomplete_samples_are_rejected(self):
  for poses in ([self.poses[0],self.poses[0]],list(reversed(self.poses)),[{'frame':0,'pose':{'pelvis':{'center':[0,0,0]}}}]):
   with self.subTest(poses=len(poses)),self.assertRaises(BridgeError):validate_params('set_pose_sequence',{**self.p,'poses':poses})
 def test_bad_last_frame_rigid_control_is_rejected_before_any_host_write(self):
  import copy
  p=copy.deepcopy(self.p);p['poses'][-1]['pose']['right_hand']['center'][0]+=250
  with self.assertRaises(BridgeError):validate_params('set_pose_sequence',p)
 def test_partial_native_visible_range_blocks_sampling_before_mutation(self):
  from cascadeur_mcp.bridge import semantics
  self.assertTrue(hasattr(semantics,'require_sampling_range'),'Missing full-range recovery preflight')
  class B:first_frame=0;last_frame=55;first_visible_frame=0;last_visible_frame=55
  class V:
   def animation_boundary(self):return B()
  class D:
   def get_animation_size(self):return 64
  class S:
   def data_viewer(self):return D()
  with self.assertRaises(BridgeError):semantics.require_sampling_range(V(),S())
  B.last_visible_frame=63
  with self.assertRaises(BridgeError):semantics.require_sampling_range(V(),S())
 def test_boolean_is_not_coerced(self):
  for value in (1,'true',None):
   with self.subTest(value=value),self.assertRaises(BridgeError):validate_params('set_pose_sequence',{**self.p,'sampled_motion':value})
 def test_explicit_bounded_skeleton_read_option(self):
  p={'character_id':self.p['character_id'],'include_track_sections':False}
  try:actual=validate_params('get_character_skeleton',p)
  except BridgeError as e:self.fail('Missing bounded skeleton option: '+str(e))
  self.assertEqual(actual,p)
if __name__=='__main__':unittest.main()
