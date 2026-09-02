# Pushd API Coverage Matrix

**Scope:** the full `api.pushd.com/v5` surface this client wraps (`auraframes/api/*.py`), not just Phase 10's endpoints.
**Created:** 2026-08-25, to satisfy the blocking `api-coverage.verify-pre` gate before Phase 10 UAT.
**Surface:** 33 wrapped capabilities — **9 INTEGRATE**, **24 OPT-OUT**.

Counted as wrapper methods, not URLs: a few paths carry two verbs (`/frames/{id}.json` is both `get_frame` and `update_frame`), so 33 capabilities span 30 distinct paths.

The API is unofficial and reverse-engineered, so "the API surface" means *what this client wraps*: there is no vendor spec to enumerate against. Endpoints the official app uses but we have never wrapped are out of scope by definition.

- **INTEGRATE** — reachable from a shipped CLI verb (`status` / `inspect` / `sync` / `push`); we own, test and live-verify it.
- **OPT-OUT** — wrapped in the client library but deliberately unreachable from any CLI verb. Kept because it documents the API, not because the product uses it.

Capability names below are the wrapper method plus its endpoint.

## Reachable from the product

| capability | decision | reason |
|---|---|---|
| AccountApi.login — POST /login.json | INTEGRATE | Auth for every verb. Live-verified repeatedly. |
| FrameApi.get_frames — GET /frames.json | INTEGRATE | Backs `status` and frame resolution in all verbs. Live-verified Phase 10. |
| FrameApi.get_frame — GET /frames/{id}.json | INTEGRATE | Backs `inspect`. Live-verified Phase 6. |
| FrameApi.get_assets — GET /frames/{id}/assets.json | INTEGRATE | The read side of the diff. Live-verified Phase 10 with filter=all plus the asset_settings join. |
| FrameApi.select_asset — POST /frames/{id}/select_asset.json | INTEGRATE | Upload association and the re-show loop. Live-verified Phases 8 and 10. |
| FrameApi.exclude_asset — POST /frames/{id}/exclude_asset | INTEGRATE | The hide default for `sync --apply`. Live-verified Phase 10. |
| FrameApi.remove_asset — POST /frames/{id}/remove_asset.json | INTEGRATE | Backs `sync --apply --delete`. Live-verified Phase 8 across 72 removals. |
| AssetApi.delete_asset — DELETE /assets/{id}.json | INTEGRATE | Backs `sync --apply --hard-delete`. Blast radius re-verified Phase 10 (HIDE-07). |
| AssetApi.batch_update — PUT /assets/batch_update.json | INTEGRATE | Commits uploaded asset metadata. Live-verified Phases 8 and 10. |

## Wrapped but deliberately unreachable

| capability | decision | reason |
|---|---|---|
| AccountApi.register — POST /account/register.json | OPT-OUT | Creating Aura accounts is out of product scope; this tool operates an account you already own. |
| AccountApi.delete — DELETE /account/delete | OPT-OUT | Irreversible account destruction with no product use case. Unreachable by design, as Phase 8 treated delete_asset. |
| FrameApi.update_frame — PUT /frames/{id}.json | OPT-OUT | The product syncs photos, not frame settings such as brightness, slideshow interval or matting. |
| FrameApi.show_asset — POST /frames/{id}/goto.json | OPT-OUT | Live remote control of what the frame displays is a different product from directory sync. |
| FrameApi.reconfigure — POST /frames/{id}/reconfigure.json | OPT-OUT | Effect is undocumented and unknown (the wrapper's own TODO). Not invoked until its blast radius is understood. |
| FrameApi.get_activities — GET /frames/{id}/activities.json | OPT-OUT | The activity feed is a social surface; sync diffs on content hashes, not activities. |
| FrameApi.add_playlist — POST /frames/{id}/add_playlist.json | OPT-OUT | Playlist management is out of scope; the wrapper is a stub that posts an empty body. |
| FrameApi.remove_playlist — POST /frames/{id}/remove_playlist.json | OPT-OUT | Playlist management is out of scope; the wrapper is a stub that posts an empty body. |
| AssetApi.crop_asset — POST /assets/crop.json | OPT-OUT | Editing photo framing is out of scope; the local directory is the source of truth. |
| AssetApi.update_taken_at_date — POST /assets/update_taken_at_date.json | OPT-OUT | Date correction is an editing feature; sync writes taken_at at upload time only. |
| AssetApi.get_asset_by_local_identifier | OPT-OUT | GET /assets/asset_for_local_identifier.json — superseded by md5 content-hash diffing (Phase 7), which needs no server-side local-id lookup. |
| ActivityApi.get_comments — GET /activities/{id}/comments.json | OPT-OUT | Social feature; no CLI verb surfaces comments. |
| ActivityApi.create_comment — POST /activities/{id}/create_comment.json | OPT-OUT | Social feature; no CLI verb surfaces comments. |
| ActivityApi.remove_comment — POST /activities/{id}/remove_comment.json | OPT-OUT | Social feature; no CLI verb surfaces comments. |
| ActivityApi.get_activity_assets — GET /activities/{id}/assets.json | OPT-OUT | Sync reads assets frame-scoped, not activity-scoped. |
| ActivityApi.post_activity — POST /activities/{id}/copy.json | OPT-OUT | Cross-frame copying is a separate capability from directory sync. |
| ActivityApi.delete_activity — DELETE /activities/{id} | OPT-OUT | Destructive and unreachable by design; remove_asset and exclude_asset are the supported removal paths. |
| PeopleApi.get_people — GET /people.json | OPT-OUT | Face-recognition browsing is not part of directory sync. |
| PeopleApi.get_people_assets — GET /people/all_assets.json | OPT-OUT | Face-recognition browsing is not part of directory sync. |
| PeopleApi.get_person — GET /people/{id}.json | OPT-OUT | Face-recognition browsing is not part of directory sync. |
| PeopleApi.get_person_assets — GET /people/{id}/assets.json | OPT-OUT | Face-recognition browsing is not part of directory sync. |
| PlaylistApi.get_playlist_assets — GET /playlists/{id}/assets.json | OPT-OUT | Playlists are out of scope. The wrapper also discards its response (no return), so it is dead as written. |
| NotificationApi.update_notification — POST /notifications/update_setting | OPT-OUT | Notification preferences are unrelated to photo sync. |
| NotificationApi.get_notification_settings — GET /notifications/settings/ | OPT-OUT | Unrelated to photo sync, and the wrapper is broken: the path literal starts with a stray f left inside the string. |

Non-Pushd dependencies on the INTEGRATE paths, outside this gate's subject: S3 upload to `images.senseapp.co` and per-frame SQS polling, both via Cognito anonymous identity pools.

## Defects found while compiling this matrix

Neither is in Phase 10's scope; both are recorded so they are not lost:

1. `auraframes/api/notificationApi.py:8` — the path literal is `'f/notifications/settings/'`; the `f` of an intended f-string ended up *inside* the string, so it would request a relative `f/notifications/...`.
2. `auraframes/api/playlistApi.py:8` — `get_playlist_assets` performs the GET but never returns the response.

## Review note

Every OPT-OUT above means "wrapped for documentation, not reachable from the product". If the roadmap adds a verb that needs one — frame settings, playlists, the activity feed — that endpoint moves to INTEGRATE and inherits the same obligation as the current nine: live verification before it is trusted.
