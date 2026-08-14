reinitialize
load fixtures/ep4/ep4r_rec.crg.pdb, EP4_receptor
load fixtures/ep4/ep4r_matched_poses_first5.sdf, EP4_poses, discrete=1
hide everything, all
show cartoon, EP4_receptor and polymer.protein
show sticks, EP4_poses
color gray70, EP4_receptor and elem C
color cyan, EP4_poses and elem C
orient EP4_poses
python
import pymol_plip
pymol_plip.__init_plugin__()
pymol_plip.plip_gui()
python end
plip_analyze EP4_receptor, EP4_poses, states=all
set dash_radius, .09
