# `aura-cli` — Command Reference

Complete reference for every command, flag, and exit code, with real output.

`aura-cli` talks to the Aura **cloud** API (`api.pushd.com/v5`) plus AWS S3/SQS. It never
talks to the frame over your local network — everything goes through your Aura account.

> The API is unofficial and reverse-engineered. It is undocumented and can change without
> notice. Every write path here has been exercised against a live frame, but that is a
> snapshot, not a guarantee.

## Contents

- [Global usage](#global-usage)
- [`status`](#status--check-credentials-and-list-frames)
- [`inspect`](#inspect--look-at-one-frame)
- [`sync`](#sync--make-a-frame-match-a-directory)
- [`push`](#push--upload-only-never-removes)
- [`reconcile`](#reconcile--account-for-stuck-placeholder-rows)
- [Choosing between `sync` and `push`](#choosing-between-sync-and-push)
- [Environment variables](#environment-variables)
- [Exit codes](#exit-codes)
- [Known issues](#known-issues)

## Global usage

```
usage: aura-cli [-h] [--debug] {status,inspect,sync,push} ...

options:
  -h, --help  show this help message and exit
  --debug     Show verbose loguru request/response logging on stderr
```

`--debug` sits on the root parser, so it goes **before** the subcommand:

```bash
uv run aura-cli --debug status      # correct
uv run aura-cli status --debug      # error: unrecognized argument
```

Without `--debug` the CLI is quiet: normal runs print only the report. With it, every HTTP
request and response is logged to stderr (secrets are redacted). A full log of every run is
always written to `logs/file_{timestamp}.log` regardless of the flag.

### The `--frame` argument

`--frame` accepts a **case-insensitive substring of the frame name**, or an exact frame id:

```bash
uv run aura-cli inspect --frame "living"                                  # substring
uv run aura-cli inspect --frame "00000000-0000-0000-0000-000000000000"    # exact id
```

Resolution rules:

| Situation | Behaviour |
|---|---|
| Exactly one name matches | Resolved |
| More than one name matches | **Ambiguous** — the run stops and lists the matches. The id fallback is *not* attempted. |
| No name matches | Falls back to an exact, case-sensitive id match |
| Still nothing | Not found — every frame on the account is listed so you can pick |

Ambiguity is never resolved silently, so a loose substring can't quietly target the wrong
frame.

## `status` — check credentials and list frames

```
usage: aura-cli status [-h]
```

The first command to run. It checks your credentials are present, logs in, and lists your
frames. Nothing is ever written.

```bash
uv run aura-cli status
```

```
AURA_EMAIL: set
AURA_PASSWORD: set
Logged in as you@example.com
1 frames:
  - Living Room (id: 00000000-0000-0000-0000-000000000000)
```

The credential check runs **before** any network call, and prints only `set` / `NOT SET` —
never the password itself. If either is missing, it stops there and exits `1`:

```
AURA_EMAIL: set
AURA_PASSWORD: NOT SET
```

## `inspect` — look at one frame

```
usage: aura-cli inspect [-h] --frame FRAME

options:
  --frame FRAME  Frame name (substring) or id
```

Read-only. Shows the frame, its owner, contributors, and the first 10 photos.

```bash
uv run aura-cli inspect --frame "Living Room"
```

```
Frame: Living Room (id: 00000000-0000-0000-0000-000000000000)
Owner: Your Name <you@example.com>
Contributors (0):
Assets: 172
Photos (showing 10 of 154, API order):
  - a1b2c3d4-1111-11f1-8000-0aaaaaaaaaaa | b5c6d7e8-2222-4333-9444-0bbbbbbbbbbb.jpg | 2026-07-04 19:41:13.922000
  - c9d0e1f2-3333-7444-8555-0ccccccccccc | None | None
Placeholder rows: 58 (run `aura-cli reconcile --frame ...` for detail)
```

Two things in that output are worth understanding, and both are server-side quirks rather
than bugs in this client — see [Known issues](#known-issues):

- **`Assets: 172` but `showing 10 of 154`.** The frame's own asset count and the number of
  assets the listing returns disagree.
- **Rows with `None | None`.** Placeholder rows: assets that were registered but whose image
  upload never completed. They have no filename, no date, and never display on the frame.

## `sync` — make a frame match a directory

```
usage: aura-cli sync [-h] --frame FRAME [--apply] [--yes] [--delete | --hard-delete] dir

positional arguments:
  dir            Local directory to scan for photos

options:
  --frame FRAME  Frame name (substring) or id
  --apply        Execute the plan (upload + delete) instead of only printing it
  --yes          Skip the confirmation prompt (required for --apply when running non-interactively)
  --delete       Remove gone-local photos from the frame instead of hiding them
                 (frame-scoped; the photo leaves this frame)
  --hard-delete  IRREVERSIBLY destroy gone-local photos instead of hiding them
                 (account-wide; requires typing the exact count to confirm)
```

`sync` makes the frame **match the directory**. Photos in the directory but not on the frame
are uploaded; photos on the frame but not in the directory are *removed from view* — how, is
what `--delete` / `--hard-delete` control.

Matching is by **md5 content hash**, not filename, so renaming a file locally does not cause
a re-upload.

### Dry run is the default

Without `--apply`, nothing changes:

```bash
uv run aura-cli sync ./photos --frame "Living Room"
```

```
Sync plan for Living Room (id: 00000000-...) — DRY RUN, nothing will be changed
To upload: 0
To hide: 96
To re-show: 0
Unchanged: 0
Already hidden: 3 (no action needed)
  - d3e4f5a6-4444-11f1-9666-0dddddddddd0 (taken 2026-07-09 06:47:55.775000)
58 frame assets without a content hash (e.g. videos) left untouched
```

Reading the plan:

| Line | Meaning |
|---|---|
| `To upload` | In the directory, not on the frame |
| `To hide` / `To delete` / `To hard-delete` | On the frame, no longer in the directory. **The verb tells you exactly which primitive will run.** |
| `To re-show` | On the frame but currently hidden, and back in the directory — it will be un-hidden, **not re-uploaded** |
| `Unchanged` | Present in both |
| `Already hidden` | Hidden and still absent locally — nothing to do |
| `...without a content hash` | Videos and placeholder rows. Never touched by sync. |

### The three removal modes

Photos no longer in the directory are **hidden by default**. The frame has no photo-count
limit, so preservation is the safe default: a mistaken sync should cost visibility, never
photos.

| Flag | Primitive | What happens | Reversible |
|---|---|---|---|
| *(none)* | `exclude_asset` | Hidden — stops displaying, stays in your account and on the frame | **Yes** — put the file back and re-run |
| `--delete` | `remove_asset` | Removed from *this frame*; the asset survives in the account | Partly — it must be re-uploaded |
| `--hard-delete` | `delete_asset` | **Destroyed account-wide** | **No** |

`--delete` and `--hard-delete` are mutually exclusive, enforced at parse time:

```bash
uv run aura-cli sync ./photos --frame "Living Room" --delete --hard-delete
# aura-cli sync: error: argument --hard-delete: not allowed with argument --delete
```

### Applying a plan

```bash
uv run aura-cli sync ./photos --frame "Living Room" --apply
```

You get one confirmation covering the whole plan, echoing the resolved frame's name and id
so a loose `--frame` substring can't apply to the wrong frame:

```
About to apply this plan to "Living Room" (id: 00000000-...). Proceed? [y/N]
```

Then the summary — again naming the verb that actually ran:

```
Uploads: 0 succeeded, 0 failed
Hidden: 1 succeeded, 0 failed
Re-shown: 0 succeeded, 0 failed
```

Failures are named individually and make the run exit `1`:

```
Hidden: 1 succeeded, 1 failed
  ! e7f8a9b0-5555-7666-8777-0eeeeeeeeeee: Client error '401 Unauthorized' for url '...'
```

### Non-interactive runs

Without a TTY, `--apply` requires `--yes` and otherwise **fails closed** rather than hanging
on a prompt:

```bash
uv run aura-cli sync ./photos --frame "Living Room" --apply < /dev/null
# --apply requires --yes when running non-interactively    (exit 1)

uv run aura-cli sync ./photos --frame "Living Room" --apply --yes   # runs
```

### The `--hard-delete` gate

Because it is irreversible and account-wide, `--hard-delete` does **not** use the y/N prompt.
It requires re-typing the exact number of photos, so you have to read the count first:

```
To hard-delete: 1
IRREVERSIBLE: 1 photo(s) will be permanently destroyed account-wide, not just removed from
this frame. This cannot be undone.
To confirm, type the number of photos to hard-delete (1): y
Aborted.
```

Answering `y` — which would satisfy any ordinary prompt — aborts. Only the exact count
proceeds:

```
To confirm, type the number of photos to hard-delete (1): 1
Hard-deleted: 1 succeeded, 0 failed
```

`--yes` skips this gate like any other. **Be deliberate**: `sync --apply --yes --hard-delete`
destroys every frame photo missing from the directory, with no prompt.

### Restoring a hidden photo

Because hiding is reversible and hidden photos still count as present for deduplication, the
round trip is just moving the file:

```bash
mv ./photos/sunset.jpg /tmp/                                        # hide it
uv run aura-cli sync ./photos --frame "Living Room" --apply --yes   # -> To hide: 1

mv /tmp/sunset.jpg ./photos/                                        # bring it back
uv run aura-cli sync ./photos --frame "Living Room" --apply --yes   # -> To re-show: 1
```

The second run reports `To upload: 0` — the photo is re-shown, never uploaded a second time.

## `push` — upload only, never removes

```
usage: aura-cli push [-h] --frame FRAME [--apply] [--yes] [--limit LIMIT]
                     [--batch-size BATCH_SIZE] [--chunk-delay CHUNK_DELAY]
                     [--max-wait MAX_WAIT] [--no-wait] [--country COUNTRY]
                     [--ignore-budget]
                     dir

positional arguments:
  dir                      Local directory of photos to upload (a supply/"buffet"; the
                           frame is NOT synced to match it)

options:
  --frame FRAME            Frame name (substring) or id
  --apply                  Execute the upload instead of only printing the plan
  --yes                    Skip the confirmation prompt (required for --apply when running
                           non-interactively)
  --limit LIMIT            Upload at most N photos this run
  --batch-size BATCH_SIZE  Assets per select_asset/batch_update call (default 50)
  --chunk-delay CHUNK_DELAY  Seconds to pause between write chunks (default 5)
  --max-wait MAX_WAIT      Max seconds to wait for write budget before stopping (default 3600)
  --no-wait                Stop immediately instead of waiting when the write budget is exhausted
  --country COUNTRY        Override the expected account country for the geo pre-flight guard
  --ignore-budget          Escape hatch: bypass the write budget entirely for this run
```

`push` is **structurally additive**: the removal list is forced empty, so it can never hide,
remove, or re-show anything. It is the safe way to add photos from a supply directory without
the frame being diffed to match it.

```bash
uv run aura-cli push ./buffet --frame "Living Room"
```

```
Push plan for Living Room (id: 00000000-...) — additive (no deletes), DRY RUN, nothing will be changed
To upload: 4
To delete: 0 (additive mode — existing frame photos left untouched)
Unchanged: 0
  + ./buffet/probe_A.jpg
53 frame assets without a content hash (e.g. videos) left untouched
```

```bash
uv run aura-cli push ./buffet --frame "Living Room" --apply --yes
```

```
Uploads: 4 succeeded, 0 failed
```

Photos already on the frame are skipped by md5, so re-running `push` on the same directory
uploads nothing.

### Pacing flags

These exist because the API has an anti-abuse layer that counts **requests**, not photos.
Batching matters far more than sleeping: at `--batch-size 50`, fifty photos cost about two
requests.

| Flag | Default | Use it when |
|---|---|---|
| `--limit N` | all | You want a controlled probe rather than the whole directory |
| `--batch-size N` | 50 | Rarely. Lowering it multiplies your request count. |
| `--chunk-delay S` | 5 | You want to spread a very large upload out further |

### Write budget and geo guard

`push` and `sync --apply` both run a client-side token-bucket budget and a geo pre-flight
check before any write, so the anti-abuse lockout is difficult to reach by accident. The
budget is persisted between runs under `AURA_STATE_DIR`.

| Flag | Effect |
|---|---|
| `--max-wait S` | Cap how long a run will wait for the budget to refill (default 3600) |
| `--no-wait` | Don't wait at all — stop as soon as the budget is dry |
| `--country XX` | Expected account country for the geo check (default `AURA_COUNTRY`) |
| `--ignore-budget` | Bypass the budget entirely. Escape hatch. |

When the budget runs dry:

```
Write budget exhausted, come back in ~40 min (or pass --no-wait / raise --max-wait).
```

When the exit IP country doesn't match:

```
VPN/exit IP in BE, account expects FR — switch your VPN and retry.
```

The geo check only runs if `AURA_COUNTRY` (or `--country`) is set; unset means skipped.

> These flags live on `push` only. `sync --apply` still gets the same budget and geo
> protection — it just takes its settings from the environment rather than per-run flags.

## `reconcile` — account for stuck placeholder rows

```
usage: aura-cli reconcile [-h] --frame FRAME [--remove] [--yes]
                          [--mechanism {remove,hard-delete,complete}]
                          [--max-age-hours MAX_AGE_HOURS]

options:
  --frame FRAME         Frame name (substring) or id
  --remove              Attempt removal of stuck placeholder rows instead of
                        only reporting them
  --yes                 Skip the confirmation prompt (required for --remove
                        when running non-interactively)
  --mechanism {remove,hard-delete,complete}
                        Which removal mechanism to attempt -- no mechanism is
                        yet confirmed to work on these rows
  --max-age-hours MAX_AGE_HOURS
                        Minimum age in hours for a placeholder row to be
                        reported as stuck rather than recently created
                        (default 24)
```

`reconcile` is **data hygiene on existing frame state**, deliberately separate from `sync`/
`push`: it accounts for the placeholder rows described in
[Known issues](#known-issues) — rows a failed or abandoned upload left behind, with no
filename, no upload date and no content hash.

A placeholder is identified narrowly: `uploaded_at`, `file_name` and `md5_hash` must **all**
be null. A video (hashless by design, but it does have a filename and an upload date) or a
row still mid-upload-processing trips at most one of the three and is never counted.

### Report (the default)

```bash
uv run aura-cli reconcile --frame "Living Room"
```

```
Frame: Living Room (id: 00000000-...)
Assets scanned: 172
Placeholder rows: 58
  stuck (older than 24.0h): 58
  recently created (may still be processing): 0
  creation time unknown: 0
    - e7f8a9b0-5555-7666-8777-0eeeeeeeeeee
    - ...
```

Rows younger than `--max-age-hours` (24h default) are reported separately as **recently
created** and are never treated as removable — a row created seconds ago by a legitimate
in-progress upload has the exact same null shape as a genuinely stuck one. A row whose
creation time cannot be determined at all is treated the same way: reported, never
removable. This is `inspect`'s single placeholder-count line in detail, computed by the
exact same function so the two numbers can never disagree.

Without `--remove`, `reconcile` performs **no write of any kind** — it only reads.

An empty asset listing is refused with a named error rather than reported as zero
placeholders, since the two are indistinguishable from an API response alone.

### `--remove`

`--remove` is required to attempt any write; without it, `reconcile` cannot mutate anything.
**No removal mechanism is yet confirmed to clear these rows** — the two existing primitives
are already known not to: `delete_asset` (`--mechanism hard-delete`) returns success and
removes nothing, and `remove_asset` (`--mechanism remove`, the default) returns "not found".
A third, untried option — `--mechanism complete` — is reserved for treating a stuck row as
an unfinished upload to *finish* (filling in real `file_name`/`md5_hash`/`uploaded_at` so it
becomes an ordinary asset the existing hide/remove paths already handle) rather than a bad
row to delete; it is not yet implemented and raises until a future plan's live probe
determines whether it's viable. Which mechanism will eventually work — if any — is the
honest open question `--remove` exists to answer.

Only the **stuck** bucket is ever a removal candidate — recently-created and unknown-age
rows are structurally unreachable from the removal code path, whatever `--mechanism` or
confirmation you give.

```bash
uv run aura-cli reconcile --frame "Living Room" --remove
```

```
Assets scanned: 172
Placeholder rows: 58
  stuck (older than 24.0h): 58
  ...
About to attempt removal of 58 stuck row(s) on "Living Room" (id: 00000000-...) using mechanism "remove". Proceed? [y/N]
```

```
Removed: 0 succeeded, 58 failed
  ! e7f8a9b0-5555-7666-8777-0eeeeeeeeeee: Client error '404 Not Found' for url '...'
  ...
```

`--mechanism hard-delete` uses the same escalated, exact-count-typing confirmation
`sync --hard-delete` does — irreversible, account-wide, no y/N shortcut — since a wrongly-run
hard-delete destroys real photos, not placeholder rows.

Without a TTY, `--remove` requires `--yes` and fails closed exactly like `sync`/`push --apply`.

**Candidate cap.** A single `--remove` run refuses to act on more than 25 stuck rows at
once — no removal mechanism is confirmed to work, so a first live attempt is a bounded,
time-boxed probe rather than a bulk operation that could either burn a large write budget on
a mechanism that does nothing, or (if a mechanism turns out to be more destructive than
expected) act on every stuck row on the frame in one run. `reconcile` reports this refusal
as a named error rather than silently truncating the candidate list.

`--remove` draws from the same account-wide write budget as `sync --apply`/`push --apply`
(see [Write budget and geo guard](#write-budget-and-geo-guard)) and paces its requests the
same way.

## Choosing between `sync` and `push`

|  | `sync` | `push` |
|---|---|---|
| Uploads new photos | Yes | Yes |
| Can remove/hide photos | **Yes** | **Never** |
| Frame ends up matching the directory | Yes | No |
| Use for | A directory that *is* the intended frame contents | A supply directory you're adding from |

If you are not sure, use `push`. It cannot take anything away.

## Environment variables

Read at import time from the environment; a `.env` file at the project root is loaded
automatically. `.env` is gitignored — never commit real credentials.

**Required**

| Variable | Purpose |
|---|---|
| `AURA_EMAIL` | Account email |
| `AURA_PASSWORD` | Account password (plaintext) |

**Optional — write budget and geo guard**

| Variable | Default | Purpose |
|---|---|---|
| `AURA_COUNTRY` | *(unset)* | Expected account country for the geo pre-flight check. Unset disables the check. |
| `AURA_GEO_FAIL_OPEN` | `true` | If the country lookup fails, continue rather than block |
| `AURA_WRITE_BUDGET_CAPACITY` | `30` | Token-bucket capacity, in requests |
| `AURA_WRITE_BUDGET_REFILL_PER_MIN` | `0.75` | Refill rate per minute |
| `AURA_WRITE_BUDGET_WAIT` | `true` | Wait for refill instead of stopping |
| `AURA_WRITE_BUDGET_MAX_WAIT` | `3600` | Max seconds to wait |
| `AURA_STATE_DIR` | `~/.config/auraframes` | Where the persisted budget lives |

**Optional — client identity**

| Variable | Default |
|---|---|
| `AURA_LOCALE` | `en-US` |
| `AURA_APP_IDENTIFIER` | `com.pushd.client` |
| `AURA_DEVICE_IDENTIFIER` | `0000000000000000` |

Booleans accept `1`, `true`, `yes`, `on` (case-insensitive); anything else is false.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success — including a dry run, and including an aborted confirmation (nothing happened, which is not a failure) |
| `1` | Missing credentials, login failure, frame not found or ambiguous, any per-item upload/removal/re-show failure, rate-limit abort, geo mismatch, or exhausted budget |

A partially-failed apply exits `1` and names each failed item. Successful work already done
is still reported.

## Known issues

### Writes intermittently fail with HTTP 401, and succeed on retry

Roughly 4 in 10 live write runs have been observed failing with a `401 Unauthorized` and
succeeding on an immediate re-run, with no change to credentials, config, or network. It
affects uploads, hides and deletes alike.

**There is no automatic retry yet.** If an apply reports 401 failures, simply run it again.
The operation is safe to repeat: uploads dedupe by md5, and hides are idempotent.

### A frame's asset count disagrees with its listing

`inspect` can report e.g. `Assets: 172` while listing `154`. The frame's own counter and the
asset listing disagree server-side. The listing is the number sync acts on.

### Placeholder rows accumulate

An asset registered by a failed or abandoned upload leaves a row with no image, no filename
and no hash — visible in `inspect` as `None | None`. They never display on the frame and sync
ignores them. They also appear to be the cause of the count mismatch above.

Run `aura-cli reconcile --frame ...` to see exactly how many a frame has, split into stuck /
recently-created / unknown-age. **No removal mechanism is yet confirmed to clear them**:
`delete_asset` returns success without removing anything, and the frame-scoped removal
returns "not found". `reconcile --remove` runs a bounded, gated probe of a removal
mechanism — see [`reconcile`](#reconcile--account-for-stuck-placeholder-rows) for the honest
current state.
