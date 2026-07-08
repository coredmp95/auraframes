# Aura Frames (PUSHD) Python Client [unofficial]

Implements most of the AuraFrames APIs in Python.

Any advice or issues are welcome.

> **Read path: VERIFIED end-to-end** against `api.pushd.com/v5` (login → list → fetch →
> download). See [`VERIFICATION-REPORT.md`](VERIFICATION-REPORT.md) for the per-step status,
> the live API drift repaired, and what is **not** verified. The upload / device flow below
> is **documented from code, NOT verified in this revive milestone.**

## Requirements

- Python 3.14 (pinned via `.python-version`) and [`uv`](https://docs.astral.sh/uv/) for
  environment, dependency, and interpreter management.
- A live Aura account (email + password) for any command that actually hits the API.

## Setup & Run (uv)

This project uses `uv` exclusively (no `pip` / `venv` / `poetry`). From a clean checkout:

```bash
# 1. Install runtime dependencies (creates .venv, respects uv.lock + .python-version).
#    uv auto-installs the pinned Python 3.14 interpreter on first sync if needed.
uv sync

# 2. Run the read-path demo (login -> list frames -> fetch assets -> download one image).
#    With AURA_EMAIL / AURA_PASSWORD unset it prints a helpful message and exits cleanly.
uv run python main.py
```

To run the asserted live read-path proof, you need the **`dev` extra** (pytest +
python-dotenv live there and are **not** installed by `uv sync` alone):

```bash
# Install the dev extra, then run the 4 live read-path tests (needs real credentials):
uv sync --extra dev
uv run pytest -m live
# — or, in one shot without a separate sync step:
uv run --extra dev pytest -m live

# The credential-less default suite stays green (live tests deselected):
uv run pytest -m "not live"
```

> Documenting a bare `uv run pytest -m live` **without** `--extra dev` (or a prior
> `uv sync --extra dev`) will fail on a clean checkout — `pytest` is an opt-in extra.

## Environment Variables

Credentials are read from environment variables (see `auraframes/utils/settings.py`). Copy
`.env.sample` to `.env` and fill in your credentials for the live test path (`.env` is
gitignored — never commit real secrets); shell-exported variables also work and take
precedence.

**Required:**
- `AURA_EMAIL`: The email of the account to authenticate with.
  - `Aura.login` may optionally be called with an email and password instead of setting env vars.
- `AURA_PASSWORD`: The password of the account to authenticate with.

**Optional (with defaults):**
- `AURA_LOCALE`: The locale of the device to mimic. (Default: `en-US`)
- `AURA_APP_IDENTIFIER`: The identifier of the aura app. (Default: `com.pushd.client`)
  - This may change between iOS and Android app implementations, untested.
- `AURA_DEVICE_IDENTIFIER`: The unique identifier of the device to mimic. (Default: `0000000000000000`)
  - Ideally this should be set to your unique identifier, though it accepts others.

## CLI Usage (`aura-cli`)

A small CLI wraps the library (installed as the `aura-cli` entry point by `uv sync`):

```bash
# Health check: config/auth + list your account's frames.
uv run aura-cli status

# Inspect a frame's photos and metadata (read-only). --frame takes a name substring or id.
uv run aura-cli inspect --frame "Living Room"

# Diff a local directory against a frame (DRY RUN by default -- prints the plan, changes nothing).
uv run aura-cli sync ./photos/ --frame "Living Room"

# Actually apply the sync (uploads new files AND deletes frame photos absent locally).
# Requires --yes to run non-interactively.
uv run aura-cli sync ./photos/ --frame "Living Room" --apply --yes

# ADDITIVE upload from a supply ("buffet") directory -- NEVER deletes anything on the frame.
# Photos already on the frame are skipped by md5; only new files upload.
uv run aura-cli push ./buffet/ --frame "Living Room" --apply --yes

# Probe flags on `push` (for the anti-abuse write budget -- see below):
#   --limit N         upload at most N photos this run
#   --batch-size N    assets per select_asset/batch_update call (default 50)
#   --chunk-delay S   seconds to pause between write chunks (default 5)
uv run aura-cli push ./buffet/ --frame "Living Room" --apply --yes --limit 40 --batch-size 5
```

Add `--debug` before the subcommand for verbose request/response logging.

## Write Path (upload) — status & anti-abuse budget

> **Partially live-exercised (v2.0), with an important caveat.** Uploads DO work: the
> batched write path successfully registered assets against a live frame. But a large
> first-time bulk import hits an **undocumented server-side anti-abuse write budget**.

Key findings (from live runs + decompiling the official Android app):

- `select_asset` and `batch_update` are **native batch endpoints** — the client now sends a
  whole chunk of assets per call (`WRITE_BATCH_SIZE`, default 50) instead of one call per
  file, collapsing ~3N Pushd write calls to ~2 per chunk.
- The account has a rolling **write-volume budget** over a time window (≈50 new assets
  observed before a trip). Exceeding it returns a bare `401`/custom `475` (no `Retry-After`),
  which the client detects as a run of consecutive failures and **aborts loudly** rather than
  hammering. The official app never trips this because it drip-feeds uploads via a background
  `JobScheduler` queue over time (gated on charging + WiFi), retrying failures across runs.
- Consequence for bulk imports: use `push --limit` in **small waves spaced over time** rather
  than one big burst. `sync`/`push` are resumable — the md5 diff means re-running only
  attempts what is still missing. Full live end-to-end verification of a large import is still
  pending a rested account.

## iOS/Android Device's Upload Image Flow

> **Documented from code, NOT verified in this revive milestone.** The flow below is
> transcribed from the 2023-era implementation and has not been exercised against the live
> API during the read-path revive. Treat it as a reference, not a proven path. NOTE: the
> current CLI write path **batches** steps 4–9 across many assets per call (see *Write Path*
> above); the per-asset sequence below is the original single-asset reference.

[Aura.upload_image](auraframes/aura.py#L101) attempts to implement this flow as closely as possible.
1. A frame is selected and the frame's data is retrieved from the API (`/frames/<frame_id>.json`).
2. An image on the device is selected for upload.
3. An Asset object is created for the image and a GUID (`local_identifier`) is generated.
4. A POST request is made (`/frames/<frame_id>/select_asset.json`) with the asset's `local_identifier`.
   - This allows the asset to be related to a specific frame once the image has been uploaded.
5. SQS is polled (may not be necessary)
   - The result does not seem to be used in a meaningful way.
6. Another `select_asset.json` request is sent with the same information.
7. A `put_object` request is made to the S3 bucket `images.senseapp.co` with the image, the MD5 and uploaded filename are retrieved.
8. The asset object is populated with the S3 response.
9. A PUT request is sent to `/assets/batch_update.json` with the asset information.
    - I believe this is when the location exif data is read from the image file itself and used to populate future asset requests. Manually populating the exif data on the Asset object before sending it does not get returned in future requests.
    - The height and width of the image can be spoofed in the Asset object to produce skewed images, it seems like only the location exif is used.
10. SQS is polled again

```mermaid
sequenceDiagram
    Device ->>  Aura Frames API: Selects a Frame
    Aura Frames API -->> Device: Frame object
    Device ->> Device: An image is selected and <br/>an asset object is created on the device.
    Device ->> Aura Frames API: PUT request to select the asset
    Note left of Aura Frames API: The asset's local_identifier<br/>and frame id are associated.
    Aura Frames API -->> Device: The number of assets that failed to associate
    Device ->> SQS: Polls queue
    Note left of SQS: The result does not seem to be used<br/>in a meaningful way.
    Device ->>  Aura Frames API: PUT request to select the asset
    Aura Frames API -->> Device: The number of assets that failed to associate
    Device ->> S3 Bucket: The image is uploaded via put_object.
    S3 Bucket -->> Device: The uploaded filename and MD5 of the image.
    Device ->> Device: Populates the Asset object with the S3 data.
    Device ->> Aura Frames API: The Asset object is uploaded.
    Note left of Aura Frames API: The image's exif data is used for the Asset's location.
    Device ->> SQS: Polls queue
```

## iOS/Android Device's Download/View Image Flow

> **VERIFIED end-to-end this milestone** (READ-01..READ-04) — see
> [`VERIFICATION-REPORT.md`](VERIFICATION-REPORT.md). `main.py` drives exactly this path.

1. A frame is selected and the frame's data is retrieved from the API (`/frames/<frame_id>.json`).
2. A paginated list of assets is retrieved with the `frame_id` (`/frames/{frame_id}/assets.json`).
3. A URL is built that contains the image proxy URL, the asset's uploaded user id, and the asset's S3 filename.
   - See [export.py](auraframes/export.py)
4. The image is retrieved from the URL.
5. TODO: Describe rendering

### TODOs

> These are open reverse-engineering notes — **documented from code, NOT verified in this
> revive milestone.**

- Map out the actual SQS flow.
  - SQS may be polling constantly and used for push notification / update requests.
- Determine if it's possible to have 2 active logins for the same account
- Is it possible to associate an asset to multiple frames? Currently, the device flow uploads the image for each frame, there may be some backend process to dedupe them.
  - Worth checking if the Asset's (S3) filename changes.
- Reverse the _actual_ frame's rendering process. Presumably it uses the same endpoints.
  - Worth checking with MITM proxy before JTAG/firmware dumping.

## Credits

This is an unofficial, reverse-engineered client.

- **Original author:** [zmanowar](https://github.com/zmanowar) (`zach@codehooker.com`) — created
  the original Aura/Pushd Python client in 2023, including the reverse-engineered API models,
  the auth/read/upload flows, and the first version of this README. All of the reverse-
  engineering insight this project builds on is his work.
- **Revive & extend (2026):** Fabrice DIDIERJEAN — modernized the ~3-year-old codebase onto
  Python 3.14 + `uv`, verified the read path live, and built the `aura-cli`
  (`status`/`inspect`/`sync`/`push`) CLI plus the batched, anti-abuse-aware write path.