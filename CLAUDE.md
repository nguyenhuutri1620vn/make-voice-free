# CLAUDE.md

Working rules for Claude Code in this repository. Read this file and `docs/raw_requirement.md` before any change. Requirement IDs (C-xx, FR-xx, NFR-xx, AC-xx) refer to that document.

## Project in one paragraph

`history-voice` is a Python CLI that turns the narration exported by `history-shorts` (`export-narration` → `manifest.json` + `<id>.txt`) into one voice file per slide plus an `audio_manifest.json` that `history-shorts render --audio` reads. Voices come either from files the owner made (VoiceStudio UI, own recording → `import`) or from a local TTS engine (`build`). The two projects share **files only**.

## Contract source of truth

The file formats are defined in the history-shorts spec, Appendix A.1 (`../make-video-free/docs/raw_requirement.md`, v2.0.3). This repo's §6.1–6.2 copy it. If the two disagree, history-shorts wins: stop and tell the owner. Never change the contract here first. Never import code from `../make-video-free`.

## Hard rules

1. **Text is read-only.** Never write to the narration directory. Copy `text_sha256` from the narration manifest after verifying it against the `.txt` bytes; never recompute it from normalised or edited text. (C-02)
2. **No network at runtime**: never import `requests`, `httpx`, `urllib.request`, `http.client`, `socket`, `huggingface_hub` download APIs in `history_voice/`. Engines run with offline flags; a missing model is an error with an install hint, never a download. (C-03)
3. **AI only in `history_voice/engines/`.** The core imports no ML library (`torch`, `transformers`, `onnxruntime`, …); `check`, `import`, `normalize` work with no engine installed. (C-04)
4. **Dependencies are fixed**: Python ≥ 3.10, `numpy`, system `ffmpeg`/`ffprobe` ≥ 4.4; dev: `pytest`, `ruff`, `mypy`, `pytest-cov`. Engine packages only as optional extras. Ask before adding anything. (C-05)
5. **Licence guard and consent**: every engine declares its model licence and `commercial_ok`; never weaken the guard. Voice cloning needs `consent: true` in the profile. Never bundle voices or reference audio. (C-06, C-07)
6. **No mixing, ducking, loudness normalisation, or timing**: that belongs to history-shorts. Here: trim, pauses, peak limit only. (§1.4)
7. **No `shell=True`**; FFmpeg and engine commands are `list[str]`. (C-09)
8. **Never delete or overwrite files outside `--out`, the cache dir, and the temp dir.** (C-08)
9. **Do not copy code from AGPL projects** (e.g. VoiceStudio) into this repo.

## Commands

```bash
# setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # core only; engines: pip install -e ".[dev,<engine>]"

# run (paths relative to this repo)
python -m history_voice check  --narration ../make-video-free/output/narration/manifest.json --out voice/
python -m history_voice import --narration ../make-video-free/output/narration/manifest.json --from ~/Downloads/voicestudio --out voice/
python -m history_voice build  --narration ../make-video-free/output/narration/manifest.json --out voice/ --voice voices/owner.json
python -m history_voice normalize --text "Năm 40 TCN [pause 400ms] Hai Bà"

# quality gates — all must pass before a task is done
ruff check . && ruff format --check .
mypy --strict history_voice
pytest -q

# inspect an output file
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,sample_fmt -show_entries format=duration -of default=nw=1 voice/s01.wav
```

## Architecture

```
contract.py     narration + audio manifests → frozen dataclasses; all contract validation here
status.py       ok / missing / stale / invalid / orphan (pure)
textprep/       pauses, numbers_vi, dictionary, prepare (all pure, no I/O except loading the dictionary)
profile.py      voice profile + consent check
engines/        Engine protocol, ENGINES registry, fake engine, real engines (only place with ML imports)
audio.py        numpy assembly of chunks + silences, peak limit
ffmpeg.py       discovery, version check, convert/trim/probe builders, run with stderr capture
cache.py        chunk cache keyed by engine/model/profile/text/seed
importer.py     import workflow
builder.py      build workflow
report.py       voice_report.json
cli.py          sub-commands, exit codes, summary output (only module that prints)
```

Data flows one way: `contract` → `status` → (`importer` | `builder` → `textprep` → `engines` → `audio`) → `ffmpeg` → write manifest + report.

## Audio rules

- Output: WAV PCM s24le, mono, 48 kHz, `<id>.wav`; written atomically (temp then rename). (FR-60, FR-64)
- Engines return float32 mono arrays at their own rate; resample and encode only in `ffmpeg.py`.
- Trim silence at −50 dBFS keeping 50 ms, then add pause-marker silences back. Pauses are exact digital silence. (FR-61, FR-20)
- Limit peaks to −1 dBFS only when exceeded; no LUFS normalisation. (FR-62)
- Segment length must be 0.3–14.0 s; fail with a suggestion to split the narration. (FR-63)

## Text rules (Vietnamese)

- Preparation works on a copy; the original `.txt` and its hash never change.
- Order: pause split → pronunciations → abbreviations → numbers → cleanup → length split.
- Dictionary matches are whole-word, case-sensitive, longest first.
- Numbers: defaults "linh" and "tư", configurable; cover 0–999 999 999 with tests for the tricky cases (10, 15, 21, 24, 105, 1428, 40 000).
- Do not "improve" the narration wording; that is the script author's job in history-shorts.

## Determinism and cache

- Cache key = `sha256(engine id, engine version, model id, profile hash, prepared chunk text, seed)`. Change any part → miss.
- Seed every engine call from `profile.seed` + chunk key. No time-based seeds, no global `random`.
- Same inputs + warm cache → byte-identical WAVs, manifest, and report (except timings).

## Coding conventions

- Python 3.10+, full type hints, `mypy --strict` clean; `@dataclass(frozen=True, slots=True)` for contract, profile, and config types.
- `pathlib.Path` everywhere; paths in manifests and profiles resolve relative to the referencing file.
- `logging` for diagnostics; only `cli.py` prints. Exceptions from `errors.py`, mapped to exit codes in `cli.py`.
- Functions ≤ ~50 lines where practical; separate pure logic from FFmpeg/engine I/O.
- Identifiers, logs, errors, docs: English. Spoken text and dictionary entries: Vietnamese.

## Testing

- Unit tests for every contract rule, status case, pause/number/dictionary case.
- Contract fixtures in `tests/fixtures/contract/` mirror history-shorts A.1 examples; update them only together with the history-shorts spec.
- Command tests assert exact FFmpeg argument lists without running FFmpeg.
- Use the `fake` engine for build tests; real engines are marked `@pytest.mark.engine` and skipped when not installed.
- E2E tests run FFmpeg; mark `@pytest.mark.ffmpeg` and skip when unavailable.
- Guard tests: no network imports, no ML imports outside `engines/`, no `shell=True`, nothing written to the narration dir (make it read-only in tests).
- All test output under `tmp_path`.

## Workflow

1. State which FR/AC IDs the task covers before coding.
2. Follow milestones P0 → P4 (spec §14). Do not start the next one until the current one meets its exit criteria.
3. Small, focused changes; run ruff, mypy, pytest after each logical step.
4. For audio changes: build with the `fake` engine (and the real engine if installed), check with `ffprobe`, and list results in the report. Owner listens to real-engine output before a milestone closes.
5. If the spec is ambiguous, pick the simplest option that satisfies the acceptance criteria and log it under "Decisions" in `README.md`. Ask only if a choice would break a hard rule or change the contract.
6. A change to a CLI flag or a file format updates the spec, README, fixtures, and tests in the same change.

## Definition of done

- [ ] Covered FR/AC IDs implemented and listed.
- [ ] `ruff check .`, `ruff format --check .`, `mypy --strict history_voice`, `pytest -q` all pass.
- [ ] New behaviour has tests.
- [ ] Output files checked with `ffprobe`; contract fixtures still pass.
- [ ] README reflects user-visible changes.
- [ ] No hard rule violated.

End every task with a short report: what changed, requirement IDs, test results, audio check notes, and open issues.

## Do not

- Do not write to the narration directory or recompute hashes from edited text.
- Do not download models, voices, or audio at runtime; document setup steps for the owner instead.
- Do not add mixing, ducking, loudness normalisation, or slide timing.
- Do not commit `voice/`, `voices/*.wav`, `.cache/`, `.venv/`, or model files.
- Do not weaken tests or the licence guard to make a build pass.

## Environment notes

- macOS first (`brew install ffmpeg`). Engine installs (PyTorch etc.) can be large; if one cannot be installed, stop and report options instead of working around it.
- The sibling repo `../make-video-free` is read-only from here; use it only to read the spec and copy fixture examples.
