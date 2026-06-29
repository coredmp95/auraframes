# Coding Conventions

**Analysis Date:** 2026-06-29

## Naming Patterns

**Files:**
- Modules use `camelCase` with a capital first letter for the class they contain: `frameApi.py`, `accountApi.py`, `assetApi.py`, `baseApi.py`
- Exception: utility modules use `snake_case`: `settings.py`, `io.py`, `dt.py`
- AWS client files follow the pattern: `awsclient.py`, `s3client.py`, `sqsclient.py`
- Model files use `snake_case` for the concept they model: `asset.py`, `activity.py`, `frame.py`, `user.py`, `person.py`, `meta.py`

**Classes:**
- PascalCase throughout: `FrameApi`, `AccountApi`, `AssetApi`, `BaseApi`, `AWSClient`, `S3Client`, `SQSClient`, `ExifWriter`
- Model classes: `Asset`, `Frame`, `User`, `Activity`, `Person`, `Comment`, `Reaction`
- Enum classes: `Feature`, `ActivityType`, `ReactionType`
- Partial/variant model classes append suffix: `AssetPartialId`, `FramePartial`, `AssetSetting`, `SuggestionManifest`

**Functions/Methods:**
- `snake_case` throughout: `get_frames()`, `get_assets()`, `build_path()`, `parse_aura_dt()`, `write_model()`
- Private methods prefixed with underscore: `_set_cookies()`, `_lookup_gps()`, `_init_logger()`, `_get_path_safe_datetime()`
- Boolean properties use `is_` prefix: `is_portrait()`, `is_local_asset`

**Variables:**
- `snake_case` for local variables and parameters: `frame_id`, `asset_data`, `json_response`, `query_params`
- Constants use `UPPER_SNAKE_CASE`: `AURA_API_BASE_URL`, `AURA_API_VERSION`, `USER_AGENT`, `BUCKET_KEY`, `AURA_DT_FORMAT`
- Module-level settings use `UPPER_SNAKE_CASE`: `LOCALE`, `DEVICE_IDENTIFIER`, `IMAGE_PROXY_BASE_URL`

**Parameters:**
- Pydantic model field names use `snake_case` matching the API's JSON keys directly: `added_by_id`, `created_at`, `frame_id`
- Avoid shadowing builtins: parameter `_filter` used instead of `filter` in `PlaylistApi.get_playlist_assets()`

## Code Style

**Formatting:**
- No formatter configuration detected (no `.prettierrc`, `pyproject.toml` with black config, or similar)
- Indentation: 4 spaces (PEP 8 standard)
- Line length: not enforced by config; some lines are long (e.g., multi-line `httpx.Client()` constructor in `client.py`)

**Linting:**
- No linting config detected (no `.flake8`, `pylintrc`, `ruff.toml`, or `pyproject.toml`)
- Codebase follows PEP 8 naming but has no automated enforcement

## Import Organization

**Order observed:**
1. Standard library imports (`os`, `sys`, `json`, `uuid`, `time`, `datetime`, `io`, `typing`)
2. Third-party imports (`boto3`, `httpx`, `loguru`, `pydantic`, `PIL`, `piexif`, `geopy`, `tqdm`)
3. Local package imports (`from auraframes.api...`, `from auraframes.models...`, `from auraframes.utils...`)

**Pattern:**
- Each import group separated by blank line (observed in `aura.py`, `client.py`, `export.py`)
- Explicit named imports preferred: `from httpx import Response, Timeout`
- `from __future__ import annotations` used in files with forward references (`asset.py`, `activity.py`)

**Path Aliases:**
- None — all imports use full `auraframes.*` package paths

## Error Handling

**Patterns:**
- Minimal error handling throughout; many API error paths have `# TODO: Error handling` comments with a bare `pass` (see `accountApi.py:29`, `accountApi.py:57`)
- HTTP error responses checked via `json_response.get('error')` but not acted upon in most cases
- Broad `except:` clauses with no exception type used in `exif.py` — e.g., `except:` catches all exceptions silently, logging only via `logger.info`
- `try/except Exception as e` used in `aura.py:download_images_from_assets()` — failed assets are collected but not re-raised
- No custom exception classes defined anywhere in the codebase
- Pydantic validation is the primary mechanism for catching bad data from the API (model construction raises on invalid types)
- `AssetPartialId` uses a Pydantic `@validator` for cross-field validation: `asset.py:118`

**Example of current error handling approach:**
```python
# accountApi.py
if json_response.get('error') or not json_response.get('result'):
    # TODO: Error handling
    pass
```

## Logging

**Framework:** `loguru` (`~=0.6.0`)

**Configuration:**
- Configured once in `Aura._init_logger()` (`aura.py:131`)
- Two sinks: `sys.stderr` at `INFO` level and `logs/file_{time}.log` (all levels)
- Structured format with timestamp, level, module/function/line, message, and `{extra}` context

**Patterns:**
- `logger.info(f'...')` for HTTP request logging (called with keyword args for extra context)
- `logger.debug(f'...')` for response bodies and cookies
- `logger.error(e)` for caught exceptions in `upload_image()`
- `loguru` structured binding via keyword args: `logger.info(f'GET request to {url}', query_params=..., headers=...)`

## Comments

**When to Comment:**
- TODOs are pervasive (28+ instances) — used to mark unimplemented features, known issues, and open questions
- Inline comments explain unclear API behavior: `# Typical use of this endpoint results in a single AssetPartialId being sent per call.`
- Attribution comments for borrowed code: `# Most of the exif writing is from: <url>` (`exif.py:14`)
- Commented-out code left in place: `# logger.remove()` in `aura.py:132`

**Docstrings:**
- All public API methods in `frameApi.py`, `accountApi.py`, `assetApi.py`, `activityApi.py` have docstrings
- Format: reStructuredText (`:param name:`, `:return:`) inline style
- Docstrings document parameter semantics and known unknowns about the upstream API
- Model classes and utility functions generally lack docstrings

**Example docstring pattern:**
```python
def get_assets(self, frame_id: str, limit: int = 1000, cursor: str = None) -> tuple[list[Asset], str]:
    """
    Gets assets for a `frame_id`. The results are paginated with `limit` results per page.

    :param frame_id: Frame ID to retrieve assets
    :param limit: Maximum number of assets per page / callout.
    :param cursor: The cursor from the previous page.
    :return: List of all the assets, and the next page's cursor (will be `None` if no more pages)
    """
```

## Function Design

**Size:** Methods are small and single-purpose; most API methods are 5–15 lines

**Parameters:**
- Type hints used on all public method signatures
- Optional parameters typed with `Optional[T]` from `typing` or default `= None`
- Pydantic model instances passed as parameters rather than raw dicts: `update_frame(frame_id, frame_partial: FramePartial)`

**Return Values:**
- Typed with return type annotations on public methods
- Pydantic models returned from API calls (not raw dicts)
- Multiple return values via `tuple`: `get_frame() -> tuple[Frame, int]`, `get_comments() -> tuple[list[Comment], int, list[User]]`
- `.json()` always called immediately on httpx responses; raw `Response` objects never returned from the `Client` layer

## Module Design

**Exports:**
- No `__all__` declarations in any module
- `auraframes/models/__init__.py` and `auraframes/api/__init__.py` are empty
- `auraframes/__init__.py` is empty — consumers must import specific submodules

**Barrel Files:**
- Not used; imports go directly to source modules: `from auraframes.api.frameApi import FrameApi`

## Data Modeling

**Framework:** Pydantic v1 (`~=1.10.4`)

**Patterns:**
- All API response shapes modeled as `pydantic.BaseModel` subclasses
- Fields typed with `Optional[T]` for nullable/missing API fields
- `Any` used when field type is unknown: `burst_id: Any`, `playlist: typing.Any`
- `from __future__ import annotations` enables forward references in models
- Partial model pattern via custom `AllOptional` metaclass (`meta.py`): `class FramePartial(Frame, metaclass=AllOptional)`
- Enums used for known string-valued discriminators: `ActivityType`, `ReactionType`, `Feature`
- Pydantic `@validator` used for cross-field validation: `AssetPartialId.check_id_or_local_id`
- `.dict(include={...})` used to build API request payloads from model instances

## Configuration

**Pattern:** Module-level constants read from environment variables at import time (`utils/settings.py`)

```python
LOCALE = os.getenv('AURA_LOCALE', 'en-US')
DEVICE_IDENTIFIER = os.getenv('AURA_DEVICE_IDENTIFIER', '0000000000000000')
```

- Credentials passed via env vars: `AURA_EMAIL`, `AURA_PASSWORD`
- AWS pool IDs hardcoded as module constants (flagged as TODO to move to config)

---

*Convention analysis: 2026-06-29*
