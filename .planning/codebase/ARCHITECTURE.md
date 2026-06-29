<!-- refreshed: 2026-06-29 -->
# Architecture

**Analysis Date:** 2026-06-29

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                        Entry Point                           │
│                       `main.py`                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Facade / Orchestrator                      │
│                  `auraframes/aura.py`                        │
│  (Aura class — composes all API clients, drives workflows)   │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   API Layer  │  │   AWS Layer      │  │  Export / EXIF   │
│`auraframes/  │  │`auraframes/aws/` │  │`auraframes/      │
│   api/`      │  │                  │  │  export.py`      │
│              │  │ S3Client         │  │`auraframes/      │
│ AccountApi   │  │ SQSClient        │  │  exif.py`        │
│ FrameApi     │  │ (both extend     │  │                  │
│ AssetApi     │  │  AWSClient)      │  │                  │
│ ActivityApi  │  └─────────────────-┘  └──────────────────┘
│ PeopleApi    │          │
│ PlaylistApi  │          ▼
│ NotificationA│  ┌──────────────────┐
│ (all extend  │  │  AWS Cognito     │
│  BaseApi)    │  │  (anonymous auth)│
└──────┬───────┘  └──────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                     HTTP Client                              │
│                  `auraframes/client.py`                      │
│      (httpx with HTTP/2, session-level auth headers)         │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Aura Frames REST API                        │
│          https://api.pushd.com/v5                            │
└─────────────────────────────────────────────────────────────┘

       │  (all layers use)
       ▼
┌─────────────────────────────────────────────────────────────┐
│                     Model Layer                              │
│                  `auraframes/models/`                        │
│     Pydantic BaseModel DTOs: Frame, Asset, User, etc.        │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `Aura` | Facade; composes all API clients; drives high-level workflows (dump, clone, upload) | `auraframes/aura.py` |
| `Client` | Synchronous HTTP client; manages auth headers, cookies, request history | `auraframes/client.py` |
| `BaseApi` | Holds `Client` reference via constructor injection; base class for all API modules | `auraframes/api/baseApi.py` |
| `AccountApi` | Login, register, delete account | `auraframes/api/accountApi.py` |
| `FrameApi` | Frame CRUD, asset association, asset listing, activity listing, playlist management | `auraframes/api/frameApi.py` |
| `AssetApi` | Asset metadata updates, crop, date overrides, delete | `auraframes/api/assetApi.py` |
| `ActivityApi` | Activity comments, asset retrieval, activity deletion | `auraframes/api/activityApi.py` |
| `PeopleApi` | People (face recognition) listing and asset queries | `auraframes/api/peopleApi.py` |
| `PlaylistApi` | Playlist asset retrieval | `auraframes/api/playlistApi.py` |
| `NotificationApi` | Notification settings | `auraframes/api/notificationApi.py` |
| `AWSClient` | Base AWS client; authenticates via Cognito identity pool (anonymous) | `auraframes/aws/awsclient.py` |
| `S3Client` | Uploads images to S3 bucket `images.senseapp.co` | `auraframes/aws/s3client.py` |
| `SQSClient` | Polls per-frame SQS queues for upload confirmation signals | `auraframes/aws/sqsclient.py` |
| `ExifWriter` | Writes EXIF metadata (datetime, GPS) back into downloaded images | `auraframes/exif.py` |
| `export` | Downloads images from the Aura image proxy, handles EXIF injection and local caching | `auraframes/export.py` |
| `cache` | File-based JSON caching decorators (`@cache`, `@async_cache`) | `auraframes/cache.py` |
| `settings` | Env-var based runtime configuration | `auraframes/utils/settings.py` |

## Pattern Overview

**Overall:** Facade + Thin API Wrapper (resource-oriented)

**Key Characteristics:**
- `Aura` is the single public entry point; callers never instantiate API classes directly
- Each `*Api` class is a thin wrapper over one REST resource domain with zero business logic of its own
- Pydantic models serve as both validated DTOs and serialization targets (`.dict()` for request payloads, `**json_response` for hydration)
- AWS auth uses Cognito anonymous identity pools — no long-lived AWS credentials needed
- All HTTP is synchronous (`httpx.Client`); the codebase has acknowledged debt to migrate to async

## Layers

**Entry Point:**
- Purpose: Demonstrates or exercises the client
- Location: `main.py`
- Contains: Minimal bootstrap code
- Depends on: `auraframes/aura.py`
- Used by: Developer directly

**Facade / Orchestrator:**
- Purpose: Composes all API and AWS clients; provides workflow methods (dump, clone, upload)
- Location: `auraframes/aura.py`
- Contains: `Aura` class
- Depends on: All `*Api` classes, `Client`, `S3Client`, `SQSClient`, `ExifWriter`, `export`
- Used by: `main.py`, external callers

**API Layer:**
- Purpose: One class per REST resource; maps Python method calls to HTTP calls and hydrates Pydantic models
- Location: `auraframes/api/`
- Contains: `AccountApi`, `FrameApi`, `AssetApi`, `ActivityApi`, `PeopleApi`, `PlaylistApi`, `NotificationApi`
- Depends on: `Client` (injected), `models/`
- Used by: `Aura`

**HTTP Client:**
- Purpose: Manages a persistent `httpx.Client` session with HTTP/2, shared headers and cookies
- Location: `auraframes/client.py`
- Contains: `Client` class with `get`, `post`, `put`, `delete` methods
- Depends on: `httpx`
- Used by: All `*Api` classes via `BaseApi`

**Model Layer:**
- Purpose: Pydantic data classes representing API response shapes
- Location: `auraframes/models/`
- Contains: `User`, `Frame`, `FramePartial`, `Asset`, `AssetPartialId`, `Activity`, `Person`, `Reaction`, `Comment`
- Depends on: `pydantic`, `auraframes/utils/dt.py`
- Used by: All API classes, `Aura`, `export.py`, `exif.py`

**AWS Layer:**
- Purpose: Provides Cognito-authenticated S3 and SQS clients
- Location: `auraframes/aws/`
- Contains: `AWSClient`, `S3Client`, `SQSClient`
- Depends on: `boto3`, `botocore`
- Used by: `Aura`

**Export / EXIF Layer:**
- Purpose: Downloads images from the image proxy and injects EXIF metadata (dates, GPS)
- Location: `auraframes/export.py`, `auraframes/exif.py`
- Contains: `get_image_from_asset()`, `ExifWriter`
- Depends on: `httpx`, `piexif`, `geopy`, `Pillow`, `models/`
- Used by: `Aura.dump_frame()`, `Aura.download_images_from_assets()`

**Utilities:**
- Purpose: Shared helpers with no business logic
- Location: `auraframes/utils/`
- Contains: `settings.py` (env vars), `dt.py` (datetime formatting), `io.py` (path building, Pydantic JSON serialisation)
- Depends on: stdlib only
- Used by: All layers

## Data Flow

### Authentication Flow

1. `main.py` creates `Aura()` — `Client` is instantiated with base URL `https://api.pushd.com/v5` (`auraframes/client.py:24`)
2. `Aura.login()` delegates to `AccountApi.login()` (`auraframes/api/accountApi.py:8`)
3. `AccountApi.login()` calls `Client.post('/login.json', ...)` with email/password payload
4. Response is hydrated into `User` model; `auth_token` and `id` are extracted
5. `Client.add_default_headers({'x-token-auth': ..., 'x-user-id': ...})` attaches auth to all subsequent requests (`auraframes/aura.py:45`)

### Frame Dump / Download Flow

1. `Aura.dump_frame(frame_id, path)` (`auraframes/aura.py:65`)
2. `FrameApi.get_frame(frame_id)` → `Client.get('/frames/{id}.json')` → `Frame` model
3. `FrameApi.get_assets(frame_id)` (paginated, cursor-based) → list of `Asset` models
4. `write_model(assets, path)` serialises models to JSON via `pydantic_encoder` (`auraframes/utils/io.py`)
5. For each asset: `export.get_image_from_asset(asset, path, exif_writer)` (`auraframes/export.py:41`)
6. Image bytes fetched from `https://imgproxy.pushd.com/{user_id}/{file_name}`
7. `ExifWriter.write_exif(image, asset)` injects EXIF datetime + GPS coordinates (`auraframes/exif.py:58`)
8. Image written to disk under `{frame.name}-{frame.id}/asset_images/`

### Image Upload Flow

1. `Aura.upload_image(frame_id, image_path, asset)` (`auraframes/aura.py:101`)
2. `FrameApi.select_asset(frame_id, AssetPartialId)` — associates `local_identifier` to frame (`auraframes/api/frameApi.py:93`)
3. `SQSClient.receive_message(queue_url)` — polls frame's SQS queue (`auraframes/aws/sqsclient.py:26`)
4. `FrameApi.select_asset()` called a second time (mirrors device behaviour)
5. `S3Client.upload_file(image_bytes, '.jpg')` → `put_object` to `images.senseapp.co` (`auraframes/aws/s3client.py:30`)
6. `Asset` fields updated with S3 filename and MD5
7. `AssetApi.batch_update(asset)` → `PUT /assets/batch_update.json` (`auraframes/api/assetApi.py:9`)
8. `SQSClient.receive_message()` polled again

**State Management:**
- Auth state held inside `Client.http2_client.headers` and `Client.http2_client.cookies` (session-level mutation after login)
- No in-process cache is used at runtime; `cache.py` provides opt-in file-based JSON cache decorators

## Key Abstractions

**`Aura` (Facade):**
- Purpose: Single public interface; hides multi-step orchestration from callers
- Examples: `auraframes/aura.py`
- Pattern: Facade — aggregates `AccountApi`, `FrameApi`, `AssetApi`, `ActivityApi`, `PeopleApi`, `S3Client`, `SQSClient`, `ExifWriter`

**`BaseApi` (Base class with DI):**
- Purpose: Receives the shared `Client` instance; all resource APIs extend it
- Examples: `auraframes/api/baseApi.py` — extended by all 7 API classes
- Pattern: Constructor injection of `Client`; no interface/protocol defined

**Pydantic Models (DTOs):**
- Purpose: Validate, hydrate, and serialise API response JSON
- Examples: `auraframes/models/frame.py`, `auraframes/models/asset.py`
- Pattern: `Model(**json_response.get('key'))` for hydration; `.dict(include={...})` for request payloads

**`AllOptional` metaclass:**
- Purpose: Generates a "partial" variant of any model (all fields become `Optional`) for PATCH-style updates
- Examples: `auraframes/models/meta.py` — used by `FramePartial` in `auraframes/models/frame.py:93`
- Pattern: `class FramePartial(Frame, metaclass=AllOptional): pass`

**`AWSClient` (Base AWS auth):**
- Purpose: Fetches temporary AWS credentials from Cognito identity pools
- Examples: `auraframes/aws/awsclient.py` — extended by `S3Client` and `SQSClient`
- Pattern: Inheritance; each subclass calls `super().auth(pool_id)` then constructs its own boto3 client

## Entry Points

**`main.py`:**
- Location: `main.py`
- Triggers: Direct Python execution (`python main.py`)
- Responsibilities: Instantiates `Aura`, calls `login()`, demonstrates API usage

**`Aura` class:**
- Location: `auraframes/aura.py`
- Triggers: Instantiation by caller
- Responsibilities: Constructor wires all dependencies; `login()` must be called before any other method

## Architectural Constraints

- **Threading:** Single-threaded, synchronous throughout. `client.py:18` has a noted TODO to make it async. `SQSClient` long-polls which blocks the calling thread.
- **Global state:** `settings.py` reads env vars at module import time — values are module-level constants. `S3Client.s3_client` is a class-level attribute (`None` until `auth()` is called).
- **Circular imports:** None detected. Models depend only on each other (e.g., `asset.py` imports `user.py`); API classes import models unidirectionally.
- **Auth ordering:** `Client` headers are mutated after `login()`. Calling any API method before `Aura.login()` sends unauthenticated requests with no error guard.
- **Pagination:** Cursor-based pagination is manual — callers (or `Aura.get_all_assets()`) must loop and handle `next_page_cursor`.

## Anti-Patterns

### Hardcoded AWS Pool IDs and Bucket Name

**What happens:** `UPLOAD_IDENTITY_POOL_ID`, `SQS_IDENTITY_POOL_ID`, and `BUCKET_KEY` are string literals in `auraframes/aws/s3client.py:8-10` and `auraframes/aws/sqsclient.py:6`.
**Why it's wrong:** These are infrastructure identifiers that may need rotation or differ between environments; they cannot be overridden without code changes.
**Do this instead:** Read them from env vars via `auraframes/utils/settings.py`, matching the pattern already used for `AURA_EMAIL`, `AURA_PASSWORD`, `DEVICE_IDENTIFIER`.

### Unguarded Post-Login State

**What happens:** `Aura.upload_image()` references `self.sqsClient` (`auraframes/aura.py:110,122`) but `sqsClient` is only assigned inside `Aura.get_sqs()` on first call. No `login()` guard exists.
**Why it's wrong:** Calling `upload_image()` before `get_sqs()` raises `AttributeError`; calling any API before `login()` sends unauthenticated requests silently.
**Do this instead:** Assign all clients in `__init__`, or add an explicit guard (`if not self._logged_in: raise RuntimeError(...)`).

### Silent Error Handling in API Responses

**What happens:** `AccountApi.login()` and `FrameApi.get_assets()` check `json_response.get('error')` with a `pass` body (`auraframes/api/accountApi.py:28`, `auraframes/api/frameApi.py:43`).
**Why it's wrong:** API errors are silently swallowed; callers receive `None` or a partial object and may crash with a confusing `KeyError` or `AttributeError` downstream.
**Do this instead:** Raise a typed exception (e.g., `AuraApiError`) containing the error message so callers can handle or surface it.

## Error Handling

**Strategy:** Minimal — most errors result in exceptions propagating naturally from httpx or Pydantic. Explicit error checks exist but are stubbed with `pass`.

**Patterns:**
- `try/except Exception as e` with `logger.error(e)` used in `Aura.upload_image()` and `Aura.download_images_from_assets()` — failures are logged and assets are collected in a `failed_to_retrieve` list
- EXIF write failures silently return an empty `BytesIO` (`auraframes/exif.py:92`)
- No custom exception hierarchy exists

## Cross-Cutting Concerns

**Logging:** `loguru` (`auraframes/aura.py:_init_logger`). INFO level to stderr with structured context. DEBUG level to rotating file at `logs/file_{time}.log`. Logger is configured in `Aura.__init__`.
**Validation:** Pydantic v1 model validation on all API response hydration. No request-side validation beyond type hints.
**Authentication:** Token-based (`x-token-auth` header + `x-user-id`). Tokens obtained via `/login.json` and stored as `Client` default headers. AWS resources use Cognito anonymous identity.

---

*Architecture analysis: 2026-06-29*
