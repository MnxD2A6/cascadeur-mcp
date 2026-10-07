import sys,copy
from pathlib import Path

from cascadeur_mcp.bridge import character

def test_restore_keeps_already_recorded_callback_state_in_guarded_history(monkeypatch):
 scene=object();before={'state':0};callback={'state':1};after={'state':2};calls=[]
 monkeypatch.setattr(character,'_snapshots',{'s':{'scene':scene,'scene_id':'scene','lineage':[],'state':before,'character_id':'c'}})
 monkeypatch.setattr(character,'scene_id',lambda v:'scene')
 monkeypatch.setattr(character,'journal',lambda s:{'entries':[{'id':'one','before':before,'after':after,'callback_state':callback}]})
 current=[after];monkeypatch.setattr(character,'capture',lambda s:copy.deepcopy(current[0]))
 def undo(scene,snapshot,known):
  assert callback in known,'Recorded callback state was discarded from recovery history'
  current[0]=before;calls.append(known);return 2
 monkeypatch.setattr(character,'restore_native',undo)
 class V:
  def name(self):return 'scene'
 before['count']=64;callback['count']=64;after['count']=64
 result=character.restore(V(),scene,'s')
 assert result['restored'] and len(calls)==1
