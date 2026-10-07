import sys
from pathlib import Path

from cascadeur_mcp.bridge import playback

def test_playback_boundary_reports_native_visible_range_separately_from_data_end():
 class B:
  first_frame=0;last_frame=55;first_visible_frame=0;last_visible_frame=55
 class V:
  def __init__(self):self.b=B()
  def animation_boundary(self):return self.b
 v=V()
 assert hasattr(playback,'configure_boundary'),'Full visible native boundary configuration is missing'
 result=playback.configure_boundary(v,0,63)
 assert result['before']['last_visible_frame']==55
 assert result['after']['last_frame']==63 and result['after']['last_visible_frame']==63
