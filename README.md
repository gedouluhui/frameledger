# FrameLedger

**A timestamp is a claim. Keep the frame evidence.**

[Interactive demo](https://gedouluhui.github.io/frameledger/) · [Tampered example](https://gedouluhui.github.io/frameledger/tampered.html) · [中文](README.zh-CN.md) · [Offline example](docs/index.html) · [MIT license](LICENSE)

FrameLedger exports frames from a local video using an explicit sampling policy, then **decodes the source again** to audit the saved manifest and PNGs. It is designed for reproducible video-language-model data preparation—not faster decoding, video editing, or model evaluation.

Average FPS is not a frame-time oracle. Variable frame rates, nonzero start timestamps and ambiguous selection rules can make the image associated with “0.14 seconds” different from the one you intended.

## Try the real demo

Python 3.11 or newer:

```sh
git clone https://github.com/gedouluhui/frameledger.git
cd frameledger
python -m pip install .
frameledger demo --out demo-output
```

Open `demo-output/index.html`. The command encodes a self-authored, variable-frame-rate FFV1 video with visible frame numbers, samples it, and runs two fresh audits:

- `demo-output/valid/index.html`: the original sampling contract passes.
- `demo-output/tampered/index.html`: a deliberately changed PTS is detected.

The original video, PNGs and both manifests remain inspectable. No footage, weights or model APIs are downloaded. The committed HTML examples are real generated reports; download and open them for an installation-free view.

## Sample, then independently re-decode

```sh
frameledger sample video.mkv --times 0,0.14,0.16 --policy nearest --origin first-frame --out samples
frameledger audit video.mkv samples/manifest.json --out verification
```

Output includes `manifest.json`, lossless RGB PNGs, a machine-readable report and a standalone HTML timeline. Sampling is labeled **exported, not yet audited**. An audit result uses a new source decode, not the saved manifest as its own oracle.

### Declare the time contract

| Option | Meaning |
|---|---|
| `--origin first-frame` | Requests are relative to the first observed decoded-frame PTS |
| `--origin media` | Requests use the raw media presentation-time coordinate |
| `--policy nearest` | Choose the nearest observed PTS; exact ties select the earlier frame |
| `--policy previous` | Choose the last observed PTS not after the request |
| `--stream N` | Select the absolute video-stream index, not its position among video streams |

Decimal and rational request strings are evaluated exactly. No `index / FPS` approximation enters selection. The request domain is the closed interval from the first to the last observed PTS—not a guessed final frame duration. `previous` is not a general guarantee about a player's displayed frame, especially across gaps.

Repeated requests may select the same frame. Distinct PTS values with identical pixels remain distinct source-frame identities.

### Audit evidence

The manifest records source SHA256/name/stream, software versions, full-index digest, exact requests, selected frame index, integer PTS, rational timebase, RGB pixel digest and PNG byte digest.

The audit compares claims against fresh observations and real PNG pixels. Reports keep **declared metadata, observed source-frame facts and exported-PNG evidence separate**. A mismatched PNG is never presented as a verified source frame. Hashes establish consistency, not authenticity or a digital signature.

| Exit | Meaning |
|---|---|
| `0` | Successful export, or complete matching audit (read the reported status) |
| `1` | Complete audit found a mismatch |
| `2` | Invalid input or incomplete/incomparable verification |

A decoder-budget stop produces an `incomplete` audit report with no verified samples. A tool/decoder version difference is incomparable; a wrong pixel-format/orientation claim under the same versions is a mismatch. Source basename is part of the explicit contract: renaming an otherwise identical source is reported separately from byte identity.

## What this version does not prove

- The original recording was complete. FrameLedger observes the supplied file and refuses reported FFmpeg errors, including demuxer truncation errors; a self-consistent shortened/re-encoded file has no knowable missing history.
- That a frame selection is useful for a VLM, a benchmark is unbiased, or model predictions are correct.
- Audio synchronization, HDR/colorimetric fidelity, rotation-aware presentation, GPU behavior or browser-accurate seeking. Output is **CPU RGB24 in raw decoded orientation**.
- Cross-version decoder equality. Use the recorded tool/PyAV/FFmpeg versions to reproduce exact evidence.

Only ordinary local media is supported. UNC paths, mapped remote drives, symlinks/reparse traversal and nested media I/O are rejected. Container/protocol allowlists exclude playlist/concat/sequence workflows. These checks are **not an OS security sandbox**: use up-to-date decoders and do not treat this package as a way to safely execute arbitrary hostile codec inputs.

Defaults: 8 GiB source bytes, 250,000 decoded frames, 16,777,216 pixels/frame, 128 samples, 16 MiB manifest, 64 MiB/PNG. Full sequential decoding favors evidence over speed. The 120-second deadline is checked cooperatively between frames; it cannot interrupt a stuck native decoder or file read.

FrameLedger temporarily enables per-thread FFmpeg error capture and disables repeated-message suppression, restoring the previous logging settings afterward. Its scans are serialized in-process; do not run it concurrently with unrelated PyAV operations that change global logging. Use separate processes for parallel jobs.

Input files are read-only; output directories must be new. Reports contain video thumbnails and filenames: review your own report before sharing. There is no telemetry or runtime upload.

## Python API

```python
from frameledger.manifest import sample_video
from frameledger.audit import audit_manifest

sample_video("video.mkv", ["0", "0.14"], "samples", policy="nearest", origin="first-frame")
result = audit_manifest("video.mkv", "samples/manifest.json")
print(result["status"])  # pass, fail, or incomplete
```

## Existing tools and intended use

[PyAV](https://pyav.org/) exposes FFmpeg timestamps. [TorchCodec](https://meta-pytorch.org/torchcodec/stable/generated/torchcodec.decoders.VideoDecoder.html) already provides exact/time-based decoding and frame metadata. [FiftyOne](https://docs.voxel51.com/user_guide/using_views.html#frame-views) already offers frame views and video exploration.

FrameLedger's narrower job is a **re-decodable sampling contract with inspectable evidence**. It does not claim novel decoding or replace these libraries. If your pipeline already preserves and independently verifies all of this metadata, the extra tool may add little value.

## Development and verification status

```sh
python -m pip install . build
python -m unittest discover -s tests -v
python scripts/test_mutants.py  # requires ffprobe; works only on private copies
python -m build
```

Tests use handwritten rational selection oracles, real self-authored videos, separate ffprobe observations when available, PNG/manifest tampering, repeated truncation rejection, logging restoration, exact-fraction round trips, and failure/incomplete status checks. Optional external `ffmpeg`/`ffprobe` coverage is visibly skipped when the binaries are unavailable.

An independent first review identified boundary defects; targeted regression tests and maintainer checks cover the fixes. **Independent post-fix re-review is still outstanding** because the review service became unavailable. Treat this as an early, explicitly scoped release—not a production certification. External real-world user validation is also outstanding.

Issues are most useful with a small synthetic video, exact command, versions and expected frame identity. Do not upload private footage. New decoder/format adapters need their own timestamp and provenance contract.

## License and provenance

Original code and procedural demo media: MIT. PyAV is BSD-3-Clause; NumPy and Pillow retain their own licenses. FFmpeg components used by PyAV wheels retain the licenses of their actual builds; this repository does not bundle standalone FFmpeg binaries or redistribute a Python environment. Consult the installed dependency notices before redistributing an application bundle. AI assistance was used in implementation and review; claims are bounded by executable evidence, not authorship marketing.
