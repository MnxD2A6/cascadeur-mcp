"""Hand-authored topology-only fixture; invented IDs, no vendor geometry/data.

Tests validate name/reference guards and order independence, not native rig
acceptance. This fixture deliberately contains no transforms or skin weights.
"""
import uuid

def synthetic_skeleton():
    def ident(name):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://example.invalid/test-rig/'+name))
    parents={'pelvis':None,'stomach':'pelvis','chest':'stomach','neck':'chest','head':'neck'}
    for side in ('l','r'):
        for chain in [('chest','clavicle_'+side,'arm_'+side,'forearm_'+side,'hand_'+side),
                      ('pelvis','thigh_'+side,'calf_'+side,'foot_'+side,'toe_'+side)]:
            parents.update(zip(chain[1:],chain[:-1]))
    # Explicit independent control inventory, not imported from production POINTS.
    kinds={'pelvis':['MainPoint','AdditionalPoint'],'stomach':['MainPoint','AdditionalPoint'],
           'chest':['MainPoint','AdditionalPoint'],'neck':['MainPoint','AdditionalPoint'],
           'head':['MainPoint','DirectionPoint','AdditionalPoint']}
    for side in ('l','r'):
        for stem,parts in {'thigh':['MainPoint'],'clavicle':['MainPoint','AdditionalPoint'],
            'arm':['MainPoint'],'forearm':['MainPoint','AdditionalPoint'],
            'hand':['MainPoint','DirectionPoint','AdditionalPoint'],
            'calf':['MainPoint','AdditionalPoint'],'foot':['MainPoint','Self0Point'],
            'toe':['MainPoint','DirectionPoint','AdditionalPoint']}.items():
            kinds[stem+'_'+side]=parts
    objects=[];bindings=[]
    for joint,parts in kinds.items():
        side=joint[-2:] if joint.endswith(('_l','_r')) else ''
        stem=joint[:-2] if side else joint
        binding={'joint':ident(joint),'box_id':ident('box/'+joint)}
        for part in parts:
            name=stem+'_'+part+side
            objects.append({'id':ident(name),'name':name,'type':'Point','parent_id':None})
            prop={'MainPoint':'main_point','DirectionPoint':'direction_point','AdditionalPoint':'additional_point'}.get(part)
            if prop:binding[prop]=ident(name)
        bindings.append(binding)
    return {'scene_id':'a'*32,'character_id':ident('owner'),
            'joints':[{'id':ident(n),'name':n,'type':'Joint','parent_id':ident(p) if p else None}for n,p in parents.items()],
            'rig_objects':objects,'bindings':bindings,'point_control_ids':[o['id']for o in objects]}
