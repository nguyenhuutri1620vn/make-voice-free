# history-voice — Raw Requirements

| Field        | Value                                                                      |
|--------------|----------------------------------------------------------------------------|
| Document     | Raw Requirements Specification                                             |
| Project      | history-voice                                                              |
| Version      | 0.1.0 (draft)                                                              |
| Status       | Draft — awaiting owner review                                              |
| Owner        | Tri Nguyen                                                                 |
| Last updated | 2026-11-11                                                                 |
| Implementer  | Claude Code (working rules in `CLAUDE.md`)                                 |
| Contract     | history-shorts spec v2.0.3, Appendix A.1 (narration/audio contract)        |

---

## 1. Overview

### 1.1 Problem

`history-shorts` renders TikTok-style history videos offline and without AI. From v2.1 it can mix a voice track, but it deliberately never runs text-to-speech (its constraint C-01). Someone has to turn its exported narration text into voice files, keep them in sync with the text, and hand them back in the exact format it expects.

### 1.2 Solution

`history-voice` is a separate Python CLI that sits between `history-shorts` and a text-to-speech engine:

```
history-shorts                         history-voice                              history-shorts
export-narration ──► narration/ ──► check · import · build ──► voice/ ──► render --audio voice/audio_manifest.json
                     manifest.json                                audio_manifest.json
                     <id>.txt                                     <id>.wav
```

It reads the narration manifest, produces one voice file per narrated slide (from a local TTS engine, or by importing files the owner made in VoiceStudio or recorded), and writes `audio_manifest.json`. The two projects share **files only**.

### 1.3 Goals

| ID   | Goal |
|------|------|
| G-01 | Produce voice files and an audio manifest that `history-shorts render --audio` accepts without edits. |
| G-02 | Never let voice and text drift apart: stale or missing recordings are always detected and named. |
| G-03 | Make Vietnamese narration sound natural: correct reading of numbers, years, abbreviations, and proper names. |
| G-04 | Support the owner's two workflows: manual (VoiceStudio UI or own recording → `import`) and automatic (`build` with a local engine). |
| G-05 | Run offline at render time; regenerate only what changed. |
| G-06 | Keep the codebase typed, tested, and easy to extend with new engines. |

### 1.4 Non-goals

- Mixing, ducking, loudness normalisation, slide timing, or video work (all owned by `history-shorts`, A.1.6–A.1.7).
- Writing or editing the narration text, or fact-checking it.
- Music or sound-effect generation (possible later project; see §16).
- Cloud TTS APIs or any paid service.
- A GUI.
- Cloning the voice of any person who has not given consent.

---

## 2. Hard Constraints

| ID   | Constraint |
|------|------------|
| C-01 | **Contract first.** File formats in §6.1–6.2 follow history-shorts Appendix A.1 exactly. A change there is made in history-shorts' spec first, then here. |
| C-02 | **Text is read-only.** Never write to the narration directory. Never recompute `text_sha256` from normalised or edited text; copy it from the narration manifest after checking it against the `.txt` bytes. |
| C-03 | **No network at runtime.** `check`, `import`, and `build` make no network calls. Engine models are installed beforehand by a separate, documented setup step; engines run with offline flags (e.g. `HF_HUB_OFFLINE=1`). |
| C-04 | **AI only behind the engine boundary.** The core package (`history_voice/` minus `engines/`) imports no ML library. `check` and `import` work with no engine installed. |
| C-05 | **Dependencies.** Core: Python ≥ 3.10, `numpy`, system `ffmpeg`/`ffprobe` ≥ 4.4. Dev: `pytest`, `ruff`, `mypy`, `pytest-cov`. Engines are optional extras (`pip install -e ".[f5tts]"`). Ask the owner before adding any dependency. |
| C-06 | **Licence guard.** Each engine declares its model licence and whether commercial use is allowed. `build` refuses a non-commercial model unless `--allow-noncommercial` is given, and the report records it. |
| C-07 | **Consent.** Voice cloning uses only reference audio the owner provides and declares as their own or used with consent (`consent: true` in the voice profile). No bundled third-party voices. |
| C-08 | **Writes are confined** to the `--out` directory, the cache directory, and the temp directory. Never delete or overwrite anything else. |
| C-09 | **No `shell=True`**; FFmpeg and engine subprocess commands are `list[str]`. |

---

## 3. Users and Use Cases

| ID    | Use case |
|-------|----------|
| UC-01 | After `history-shorts export-narration`, see which slides need a recording. |
| UC-02 | Generate voices in the VoiceStudio UI (or record with a microphone), save them as `<id>.wav`, and import them. |
| UC-03 | Generate all missing/stale voices automatically with a local engine and the owner's voice profile. |
| UC-04 | Edit one slide's narration, re-export, and regenerate only that slide. |
| UC-05 | Fix the pronunciation of a name or year once in a dictionary and have it apply everywhere. |
| UC-06 | Listen to one sentence quickly before a full build. |

---

## 4. Glossary

| Term | Meaning |
|------|---------|
| Narration manifest | `manifest.json` written by `history-shorts export-narration` (§6.1). |
| Audio manifest | `audio_manifest.json` written by this tool (§6.2), read by `history-shorts render --audio`. |
| Segment | One narrated slide: one `.txt` in, one audio file out, keyed by slide `id`. |
| Chunk | Part of a segment between pause markers; synthesised separately. |
| Stale | A segment whose recorded `text_sha256` differs from the current narration manifest. |
| Voice profile | `voices/<name>.json`: engine, reference audio, speed, seed, consent (§6.3). |
| Engine | Adapter that turns one chunk of text into audio (§5.6). |

---

## 5. Functional Requirements

Priority: **M** Must · **S** Should · **C** Could.

### 5.1 CLI

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-01 | `python -m history_voice check --narration PATH --out DIR` reports every segment as `ok`, `missing`, `stale`, or `invalid`, and every orphan audio segment. Exit 0 when all `ok`, else 3. | M |
| FR-02 | `python -m history_voice import --narration PATH --from DIR --out DIR` imports owner-made files (§5.4). | M |
| FR-03 | `python -m history_voice build --narration PATH --out DIR --voice PATH` synthesises missing and stale segments (§5.5). `--force` rebuilds all; `--only ID[,ID]` limits the set. | M |
| FR-04 | `python -m history_voice say --voice PATH --text "…" --out FILE` synthesises one ad-hoc text for listening; it touches no manifest. | S |
| FR-05 | `python -m history_voice engines` lists installed engines with model, licence, and commercial flag. | S |
| FR-06 | `python -m history_voice normalize --text "…"` prints the text after Vietnamese normalisation (§5.3), for checking pronunciation. | S |
| FR-07 | `--version`; `--verbose` logs commands and per-chunk timing. | M |

### 5.2 Narration manifest loading

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-10 | Accept `kind` `"history-shorts.narration"` and `schema_version` major `1`; reject anything else (exit 3). | M |
| FR-11 | For each segment, read the `.txt` bytes and verify their SHA-256 equals `text_sha256`; mismatch → `invalid` ("narration file edited by hand; re-export"). | M |
| FR-12 | Resolve `file` relative to the manifest; reject paths outside its directory. | M |
| FR-13 | Report all problems at once, with JSON paths. | M |

### 5.3 Text preparation (Vietnamese)

Applied to a copy of the text for synthesis only (C-02).

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-20 | Split at `[pause Nms]` markers into chunks and silences (N 50–3000). Markers at the start or end become leading/trailing silence. | M |
| FR-21 | Numbers to words: integers 0–999 999 999 read in Vietnamese ("40" → "bốn mươi", "1428" → "một nghìn bốn trăm hai mươi tám", with "linh"/"lẻ" and "mốt"/"tư"/"lăm" rules; style set in the dictionary). | M |
| FR-22 | Abbreviations and fixed phrases from the dictionary ("TCN" → "trước Công nguyên", "SCN" → "sau Công nguyên"). Whole-word, case-sensitive matches. | M |
| FR-23 | Pronunciation overrides for names (e.g. a respelling the engine reads correctly) from the dictionary, applied before numbers. | S |
| FR-24 | Strip characters the engine cannot read (emoji, stray brackets) with a warning naming the segment. | M |
| FR-25 | Long chunks are split at sentence punctuation into pieces ≤ the engine's `max_chars`, joined with a short natural gap (`gap_ms`, default 120). | S |

### 5.4 Import (manual workflow)

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-30 | Match files in `--from` by stem to segment ids (`s03.wav`, `s03.flac`, `s03.mp3`, `s03.m4a`). Ambiguous matches (two files for one id) are errors. | M |
| FR-31 | Convert each match to the output format (§5.7) with FFmpeg; never modify the source file. | M |
| FR-32 | Imported segments take `text_sha256` from the current narration manifest; the report marks them `source: "import"`. The owner is responsible for having recorded the current text; `import` prints each segment's text next to its file for a final check. | M |
| FR-33 | Segments with no matching file are left as they are and reported. | M |

### 5.5 Build (automatic workflow)

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-40 | Synthesise only `missing` and `stale` segments unless `--force`/`--only`. | M |
| FR-41 | Per segment: prepare text (§5.3) → synthesise each chunk → insert silences → join → post-process (§5.7). | M |
| FR-42 | Cache chunk audio by `sha256(engine id, engine version, model id, voice profile hash, prepared chunk text, seed)`. Re-running with no change synthesises nothing. | M |
| FR-43 | Seed every engine call from `voice.seed` and the chunk key, so a rebuild with an empty cache is as repeatable as the engine allows. | M |
| FR-44 | A failure in one segment does not stop others; the audio manifest is written with the successful ones and the command exits 6, naming failures. | M |
| FR-45 | Licence guard (C-06) runs before any synthesis. | M |

### 5.6 Engines

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-50 | An `Engine` protocol: `id`, `version`, `model_id`, `licence`, `commercial_ok`, `sample_rate`, `max_chars`, `synthesize(text, voice, seed) -> float32 mono array`. | M |
| FR-51 | Engines register in an `ENGINES` dict; adding one never edits core modules. | M |
| FR-52 | A `fake` engine (deterministic tones, no ML) for tests and dry runs. | M |
| FR-53 | First real engine: chosen by the owner at P2 (candidates in §16). Runs in-process or via a `list[str]` subprocess; either way offline (C-03). | M |
| FR-54 | A missing engine or model gives an install hint and exit 6, never a download. | M |

### 5.7 Audio post-processing and output

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-60 | Output: WAV, PCM 24-bit, mono, 48 kHz, named `<id>.wav`. | M |
| FR-61 | Trim leading/trailing silence below −50 dBFS, keeping 50 ms, then re-add leading/trailing silence from pause markers (FR-20). | M |
| FR-62 | Peak-limit to −1 dBFS if the engine output clips; no loudness normalisation (owned by history-shorts). | M |
| FR-63 | Reject segments shorter than 0.3 s or longer than 14.0 s with a clear message (contract limit); suggest splitting the slide's narration. | M |
| FR-64 | Write each audio file and the audio manifest atomically (temp file then rename). | M |

### 5.8 Reporting

| ID    | Requirement | Pri |
|-------|-------------|-----|
| FR-70 | `voice_report.json` next to the audio manifest: per segment status, source (`build`/`import`), engine/model/licence, prepared text, duration, cache hit, timings. | M |
| FR-71 | Console summary: counts per status, total voice seconds, the longest segment, and the command to run in history-shorts next. | M |

---

## 6. Data Contracts

### 6.1 Narration manifest (input, owned by history-shorts)

As defined in history-shorts Appendix A.1.3:

```json
{
  "kind": "history-shorts.narration",
  "schema_version": "1.0",
  "script_title": "Nữ tướng thời Hai Bà Trưng",
  "segments": [
    { "id": "s01", "file": "s01.txt", "text_sha256": "<hex>", "chars": 142 }
  ]
}
```

`.txt`: UTF-8, no BOM, LF, NFC, one final LF. `text_sha256` = SHA-256 of the file bytes.

### 6.2 Audio manifest (output, read by history-shorts)

As defined in history-shorts Appendix A.1.4:

```json
{
  "kind": "history-shorts.audio",
  "schema_version": "1.0",
  "segments": [
    { "id": "s01", "file": "s01.wav", "text_sha256": "<hex>" }
  ]
}
```

- `file` relative to the manifest, inside its directory.
- Optional `gain_db` (−12 to +12) is written only when the voice profile sets it.
- Segment order follows the narration manifest. Existing segments for ids still in the narration manifest are kept when not rebuilt; orphan ids are dropped with a warning.
- No other keys (history-shorts warns on unknown keys); tool-specific data goes in `voice_report.json`.

### 6.3 Voice profile (`voices/<name>.json`)

| Field | Type | Req | Default | Notes |
|-------|------|-----|---------|-------|
| `engine` | string | yes | — | Key in `ENGINES`. |
| `model` | string | no | engine default | Model id or local path. |
| `reference_audio` | string | engine-dependent | — | Path relative to the profile; owner's own voice. |
| `reference_text` | string | engine-dependent | — | Transcript of the reference audio. |
| `consent` | boolean | yes for cloning | — | Must be `true` when `reference_audio` is set (C-07). |
| `speed` | number | no | 1.0 | 0.7–1.3. |
| `seed` | integer | no | 0 | |
| `gain_db` | number | no | 0 | Copied into the audio manifest. |
| `dictionary` | string | no | `dictionary/vi.json` | |

Reference audio is never committed (git-ignored `voices/*.wav`).

### 6.4 Dictionary (`dictionary/vi.json`)

```json
{
  "abbreviations": { "TCN": "trước Công nguyên", "SCN": "sau Công nguyên" },
  "pronunciations": { "Tô Định": "Tô Định" },
  "numbers": { "zero_tens": "linh", "four_units": "tư" }
}
```

Unknown keys are errors. Entries apply longest-match first.

---

## 7. CLI

```
python -m history_voice check     --narration PATH --out DIR
python -m history_voice import    --narration PATH --from DIR --out DIR
python -m history_voice build     --narration PATH --out DIR --voice PATH
                                  [--force] [--only IDS] [--allow-noncommercial]
                                  [--cache DIR] [--jobs N]
python -m history_voice say       --voice PATH --text TEXT --out FILE
python -m history_voice normalize --text TEXT [--dictionary PATH]
python -m history_voice engines
python -m history_voice --version
```

Default cache: `.cache/history-voice/` in the project directory.

| Exit | Meaning |
|------|---------|
| 0 | Success (warnings may be printed). |
| 1 | Internal error. |
| 2 | Invalid CLI usage. |
| 3 | Contract or validation error (bad manifest, stale/missing in `check`, bad profile/dictionary). |
| 4 | FFmpeg missing or < 4.4. |
| 5 | FFmpeg failed. |
| 6 | Engine missing, model missing, or synthesis failed. |
| 7 | Licence guard refused the engine (C-06). |
| 130 | Interrupted; temp files cleaned. |

---

## 8. Audio Specification

| Item | Value |
|------|-------|
| Format | WAV, PCM s24le, mono, 48 000 Hz |
| Silence trim | −50 dBFS threshold, keep 50 ms each side |
| Peak | ≤ −1 dBFS (limit only when exceeded) |
| Pause | exact N ms of digital silence |
| Chunk gap | `gap_ms` (default 120 ms) when one chunk is split by length |
| Length | 0.3–14.0 s per segment |

---

## 9. Non-Functional Requirements

| ID     | Requirement |
|--------|-------------|
| NFR-01 | Offline at runtime (C-03); guard test fails on network imports in the core. |
| NFR-02 | `check`, `import`, `normalize` run in < 2 s for 30 segments, with no engine installed. |
| NFR-03 | Repeatable: same inputs + warm cache → byte-identical outputs. |
| NFR-04 | `mypy --strict` clean, `ruff` clean, coverage ≥ 85 % of the core. |
| NFR-05 | macOS first; Windows and Linux supported for the core. |
| NFR-06 | Logging via `logging`; only `cli.py` prints. |

---

## 10. Architecture

```
history_voice/
  __main__.py
  cli.py            sub-commands, exit codes, summary (only module that prints)
  errors.py         exception types → exit codes
  contract.py       narration + audio manifests: frozen dataclasses, load/validate/write
  status.py         ok / missing / stale / invalid / orphan computation (pure)
  textprep/
    pauses.py       [pause Nms] split (pure)
    numbers_vi.py   Vietnamese number reading (pure)
    dictionary.py   load + apply abbreviations / pronunciations (pure)
    prepare.py      full pipeline, length splitting
  profile.py        voice profile loading and consent check
  engines/
    base.py         Engine protocol, EngineInfo, ENGINES registry
    fake.py         deterministic test engine
    <real>.py       first real engine (P2)
  audio.py          numpy assembly (chunks + silence), peak limit
  ffmpeg.py         discovery, convert/trim/probe command builders, run
  cache.py          chunk cache (key → .npy or .wav)
  importer.py       import workflow
  builder.py        build workflow
  report.py         voice_report.json
dictionary/vi.json
voices/             profiles (*.json committed, *.wav ignored)
tests/
  fixtures/contract/   sample manifests + .txt copied from history-shorts
```

Data flows one way: `contract` → `status` → (`importer` | `builder` → `textprep` → `engines` → `audio`) → `ffmpeg` post-process → `contract.write_audio_manifest` + `report`.

---

## 11. Error Handling

| Situation | Behaviour | Exit |
|-----------|-----------|------|
| Invalid JSON / unknown `kind` or version | File, line, JSON path. | 3 |
| `.txt` hash mismatch | Segment id, expected vs actual hash, "re-export". | 3 |
| Path outside manifest dir | Resolved path. | 3 |
| Missing `consent` with reference audio | Profile path. | 3 |
| Segment length outside 0.3–14 s | Segment id, length, suggestion. | 3 |
| Engine or model not installed | Install hint, no download. | 6 |
| Synthesis error | Segment id, chunk text, engine stderr tail. | 6 |
| Non-commercial model without flag | Model, licence, how to override. | 7 |
| FFmpeg missing / old / failed | Install hint / last 20 stderr lines. | 4 / 5 |

---

## 12. Testing Strategy

| Level | Scope |
|-------|-------|
| Unit | Pause parsing, number reading (table of cases incl. 0, 10, 15, 21, 24, 105, 1428, 40 000), dictionary longest-match, status computation, profile validation. |
| Contract | Load fixture manifests copied from history-shorts; write an audio manifest and validate it against the A.1.4 rules (keys, paths, order, hash copied). |
| Command | Exact FFmpeg argument lists without running FFmpeg. |
| Engine | `fake` engine end to end; real engines marked `@pytest.mark.engine`, skipped when not installed. |
| E2E | `@pytest.mark.ffmpeg`: build with `fake` → `ffprobe` checks format, rate, channels, length; second run hits the cache and is byte-identical. |
| Guard | No network imports in the core; no ML imports outside `engines/`; no `shell=True`; nothing writes to the narration dir (tests set it read-only). |

All test output under `tmp_path`.

---

## 13. Acceptance Criteria

| ID | Criterion | Covers |
|----|-----------|--------|
| AC-01 | `check` on a fresh export lists every segment as `missing`, exit 3; after `build` with `fake`, all `ok`, exit 0. | FR-01, 40 |
| AC-02 | Editing one narration and re-exporting makes exactly that segment `stale`; `build` regenerates only it (other chunks are cache hits). | FR-01, 40, 42 |
| AC-03 | `import` of `s01.mp3` and `s02.wav` produces 48 kHz mono 24-bit WAVs and a valid audio manifest; sources are untouched. | FR-30–32, 60 |
| AC-04 | `"Năm 40 TCN [pause 400ms] Hai Bà"` prepares to two chunks `"Năm bốn mươi trước Công nguyên"`, `"Hai Bà"` with a 400 ms silence. | FR-20–22 |
| AC-05 | The produced audio manifest passes `history-shorts validate --audio` (manual E2E across both repos, owner run). | C-01 |
| AC-06 | Two builds with a warm cache produce byte-identical WAVs and manifest. | NFR-03 |
| AC-07 | A non-commercial engine without `--allow-noncommercial` exits 7 before synthesis. | C-06 |
| AC-08 | `ruff`, `mypy --strict`, `pytest` pass; guard tests pass. | NFR-01, 04 |

---

## 14. Milestones

| Milestone | Deliverables | Exit criteria |
|-----------|--------------|---------------|
| P0 — Scaffold | Package, CLI skeleton, errors, guard tests, contract fixtures. | AC-08 (partial) |
| P1 — Contract & import | `contract`, `status`, `check`, `ffmpeg`, `audio`, `import`, report. No engine needed. | AC-01 (check part), AC-03 |
| P2 — Build | `textprep` pauses, engine protocol, `fake`, cache, `build`, licence guard; owner picks the first real engine. | AC-01, AC-02, AC-06, AC-07 |
| P3 — Vietnamese text | Numbers, dictionary, `normalize`, length splitting, `say`. | AC-04 |
| P4 — Integration | Narrated example with history-shorts M7; README workflow across both repos. | AC-05, all AC |

P1 can start before history-shorts M7: the contract is fixed, and fixtures are written by hand.

---

## 15. Licensing and Content

- Code licence: owner to choose (MIT suggested). Do not copy code from AGPL projects (e.g. VoiceStudio) into this repo; using them as separate programs is fine.
- Every engine records its model licence; the README table lists them. Owner verifies licences before commercial use.
- No bundled voices or reference audio. The owner's own reference audio stays local.
- The tool speaks whatever text history-shorts exports; historical accuracy stays the responsibility of the script.

---

## 16. Risks and Open Questions

| ID | Item | Default / mitigation |
|----|------|----------------------|
| R-01 | Engine output is not bit-reproducible across machines. | Cache + seed; NFR-03 only promised with a warm cache. |
| R-02 | Vietnamese tones misread on rare names. | Pronunciation dictionary (FR-23); `normalize` + `say` for checking. |
| R-03 | Model licences may forbid commercial use. | Licence guard (C-06). |
| R-04 | Contract drift with history-shorts. | Shared fixtures; later, JSON Schema files in `history-shorts/docs/contracts/` tested by both repos. |
| Q-01 | First real engine for P2: VoiceStudio-driven (if it exposes a CLI/API), F5-TTS Vietnamese fine-tune, viXTTS, or Piper `vi_VN`. | Owner decides at P2, after checking licences. Until then `import` covers VoiceStudio. |
| Q-02 | Number reading style ("linh" vs "lẻ", "tư" vs "bốn"). | Defaults "linh", "tư"; configurable in the dictionary. |
| Q-03 | Background music / SFX generation. | Out of scope; possible separate project later. |
