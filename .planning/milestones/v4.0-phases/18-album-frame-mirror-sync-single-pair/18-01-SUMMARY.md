---
phase: 18-album-frame-mirror-sync-single-pair
plan: 01
subsystem: google
tags: [google, cache, manifest, offline-tested]
requires:
  - auraframes/google/enumerate.py (AlbumListing items: id/base_url/width/height/ts_ms)
  - auraframes/aws/s3client.py (get_md5 — the frame's base64-MD5 convention)
provides:
  - auraframes/google/cache.py (CacheOutcome, download_to_cache, prune_cache, videos_skipped)
  - auraframes/google/manifest.py (GoogleManifest load/save/add/entry_for)
affects: [18-02 (build_demand consumes listing+manifest+staged), 18-03 (persist-after-confirm, prune after apply)]
tech-stack:
  added: []
  patterns:
    - bounded ThreadPoolExecutor with post-shutdown result merge (no shared mutable state in flight)
    - atomic 0600 manifest write (temp + os.replace + chmod repair), mirroring the cookie vault's file discipline
key-files:
  created:
    - auraframes/google/cache.py
    - auraframes/google/manifest.py
    - tests/test_google_cache.py
    - tests/test_google_manifest.py
  modified: []
key-decisions:
  - "Length verification falls back to the caller's expected_size (phase-16 Range measurement) when a transport does not populate Content-Length"
  - "prune_cache deletes BY NAME (cache_dir/<id>), never a directory walk — CSE-03 discipline extended to pruning itself"
  - "Manifest entry shape is CLOSED — load() fails loud on any extra key, so no per-id secret state can ever be smuggled in"
requirements-completed: [CSE-01, CSE-02, CSE-04, CSE-07, CSE-08, SAFE-04]
coverage:
  - deliverable: Concurrent =d downloads stage exact bytes keyed by google_media_id (CSE-01)
    verification:
      - kind: test
        ref: tests/test_google_cache.py#test_download_stages_exact_bytes_with_frame_convention_md5
        status: pass
      - kind: test
        ref: tests/test_google_cache.py#test_concurrent_workers_stage_all_items_order_independently
        status: pass
    human_judgment: false
  - deliverable: SAFE-04 — failed/partial downloads never written, never hashed, no orphans
    verification:
      - kind: test
        ref: tests/test_google_cache.py#test_failed_download_never_writes_never_hashes
        status: pass
      - kind: test
        ref: tests/test_google_cache.py#test_content_length_mismatch_is_a_failed_not_staged_download
        status: pass
    human_judgment: false
  - deliverable: Persistent manifest survives pruning with atomic 0600 closed-shape writes (CSE-02)
    verification:
      - kind: test
        ref: tests/test_google_manifest.py#test_save_then_load_round_trips_exactly
        status: pass
      - kind: test
        ref: tests/test_google_manifest.py#test_save_enforces_0600
        status: pass
      - kind: test
        ref: tests/test_google_manifest.py#test_load_rejects_extra_keys_no_secrets_escape_hatch
        status: pass
    human_judgment: false
  - deliverable: Prune deletes exactly manifest-backed files, keeps retry candidates (CSE-04)
    verification:
      - kind: test
        ref: tests/test_google_cache.py#test_prune_deletes_exactly_manifest_backed_files
        status: pass
    human_judgment: false
  - deliverable: Video skip count via metadata delta (CSE-07)
    verification:
      - kind: test
        ref: tests/test_google_cache.py#test_videos_skipped_delta
        status: pass
    human_judgment: false
  - deliverable: Progress reporting seam for downloads (CSE-08)
    verification:
      - kind: command
        ref: "download_to_cache(workers=...) bounded-pool structure reviewed; per-item progress callback deferred to plan 18-03's tqdm wiring at the CLI layer (the engine outcome carries staged/failed counts the bar advances on)"
      - kind: test
        ref: tests/test_google_cache.py#test_workers_minimum_is_one
        status: pass
    human_judgment: true
    rationale: "CSE-08's user-visible progress lands in plan 18-03's CLI wiring (tqdm over staged/failed outcomes); this plan provides the bounded pool and outcome accounting it reports on — coverage completed by 18-03."
duration: 25 min
completed: 2026-09-28
---

# Phase 18 Plan 01: Google-Side Cache & Manifest Summary

Pruned-disk download cache (bounded-pool `=d` fetches keyed by google_media_id, SAFE-04
failure accounting) + the persistent `google_media_id → md5_hash` manifest (atomic
0600, closed shape) — the primitives that make "zero uploads on run 2 despite a
pruned cache" expressible.

## Accomplishments

- `auraframes/google/cache.py`: `download_to_cache` (bounded ThreadPoolExecutor,
  default 4 workers injectable to 1; manifest members skipped entirely; per-item
  failure isolation into `CacheOutcome.failed` with orphan-file cleanup),
  `prune_cache` (deletes by name, idempotent), `videos_skipped` (metadata-delta math).
- `auraframes/google/manifest.py`: `GoogleManifest.load/save/entry_for/add` —
  absent file loads as empty, closed entry shape validated on load (extra/missing
  keys fail loud), atomic temp+rename save with 0600 enforcement (repairs pre-existing
  loose files).
- md5 computed with `auraframes.aws.s3client.get_md5` — the SAME base64-MD5
  convention the frame reports (LGS-06 chain).
- 21 offline tests; zero live network (TEST-02).

## Deviations from Plan

None - plan executed exactly as written. (One test-authoring fix mid-task: the
"httpx response without Content-Length" case needed a streamed response body since
httpx auto-derives the header from bytes bodies — test-side only, no code change.)

## Issues Encountered

None

## Self-Check: PASSED
