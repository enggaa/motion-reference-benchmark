# Optional legacy local reference baseline

This is a portable copy of the previously exercised Blender retargeter and evaluated-rig exporter, included so a successor can inspect the actual implementation rather than rely on the report. It is **not** the missing LLM planner and is not wired into the benchmark runner.

`retarget_blender.py` requires Blender with NumPy, an external 21-joint `.npy` trajectory, and a compatible `.blend` scene. The scene must contain the same `AdultMale_Rig`, `FACE_CONTROLS`, named deform bones and camera used by the local baseline. Those third-party-derived assets are intentionally not included. `--scene` is now required; hardcoded workstation paths were removed. This path portability change has not been rerun with a supplied external scene in this repository.

```bash
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
  --python reference_baseline/retarget_blender.py -- \
  --clip 01371 --source-joints private/01371.npy --scene private/character.blend \
  --continuous-limbs --preserve-initial-torso --out runs/reference --render-mode video
```

Source representation: ordered root/spine/head, left shoulder/elbow/wrist, right shoulder/elbow/wrist, left leg, right leg; stored axes are x,z,y from the original C3D world. The retargeter maps them to -x,-y,z, uses 12.5 Hz samples interpolated to 25 Hz, and preserves target bone lengths. Never pass an arbitrary dataset solely because it has shape `(N,21,3)`.

Known limits: surface-marker proxies are not exact joint centers; no finger observations; no full collision/contact/dynamic-balance solver; continuous orientation transport does not recover actual wrist pronation. Direction agreement with the supplied input is not semantic correctness. The previous malformed legacy inputs could satisfy that agreement test while visibly producing incorrect motion.

The benchmark's own procedural mannequin assets can instead be extended into a renderer without requiring this external character. Do not invent the missing assets or report these scripts as a tested unseen-action generator.
