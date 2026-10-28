# Claude continuation entry point

Read `HANDOFF.md`, `STATUS.json`, and `docs/MIDTERM_REPORT.ko.md` first.

This is enggaa's **personal private research repository**, not a company repository. Do not move it to an organization or change visibility without the owner's instruction.

The user wants an LLM between an action/keyframe dictionary and a reference-video renderer, including unseen actions and non-standing initial poses. A fixed phrase matcher or playback of three known actions is only a baseline, not the intended research result.

Critical failure to avoid: reporting that motion is fixed because self-consistency metrics pass while the visible arm goes behind the body. Check original input/initial pose, semantic requirements, evaluated geometry and actual rendered output separately.

Do not claim training, independent review, unseen-action success or I2V/R2V improvement without executed evidence. Never populate result tables with invented model scores. `null` means unrun/unresolved, not zero performance.

Do not feed `benchmark/evaluator/` or test solutions into generation, retrieval, repair or finetuning. Develop on `development`, use `calibration` for rater practice, and freeze before `test`. If test feedback is used to tune, version a new evaluation split.

Run `python -m motionbench validate` and `python -m unittest discover -s tests -v` after relevant edits. No third-party Python dependencies are needed for these. Blender is required only for asset re-rendering and the optional legacy reference baseline.
