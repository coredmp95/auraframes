# Technology Stack

**Analysis Date:** 2026-06-29

## Languages

**Primary:**
- Python 3 - All source code; confirmed Python 3.14.4 on development machine

## Runtime

**Environment:**
- Python 3 (no version pin file detected; system Python used)

**Package Manager:**
- pip with `requirements.txt`
- Lockfile: Not present (no `requirements.lock` or `poetry.lock`)

## Frameworks

**Core:**
- None - This is a standalone Python library/CLI tool; no web framework is used

**Data Validation:**
- pydantic ~=1.10.4 - All API response models and domain objects use `BaseModel`; see `auraframes/models/`

**Testing:**
- Not detected - No test files, pytest config, or test runner found

**Build/Dev:**
- None detected - No build tooling or Makefile present

## Key Dependencies

**HTTP Client:**
- httpx==0.23.1 - Primary HTTP client used in `auraframes/client.py`; HTTP/2 enabled via `httpx.Client(http2=True)`
- h2==4.1.0 - HTTP/2 protocol implementation required by httpx for `http2=True` mode
- requests==2.28.1 - Listed in `requirements.txt` but not observed in active source files; httpx is the actual client used

**AWS SDK:**
- boto3==1.26.38 - Used in `auraframes/aws/awsclient.py`, `auraframes/aws/s3client.py`, `auraframes/aws/sqsclient.py`
- botocore~=1.29.38 - AWS SDK core, used in `auraframes/aws/awsclient.py` for `botocore.config.Config`

**Image Processing:**
- Pillow~=9.5.0 - Image reading and thumbnail generation in `auraframes/aura.py` and `auraframes/export.py`
- piexif~=1.1.3 - EXIF data reading and writing in `auraframes/exif.py`

**Geocoding:**
- geopy~=2.3.0 - Reverse geocoding via Nominatim in `auraframes/exif.py`

**Logging:**
- loguru~=0.6.0 - Structured logging throughout; configured in `auraframes/aura.py` via `_init_logger()`; writes to `logs/file_{time}.log` and stderr

**Progress Display:**
- tqdm~=4.65.0 - Progress bars for batch download operations in `auraframes/aura.py`

## Configuration

**Environment:**
- Configured exclusively via environment variables, read in `auraframes/utils/settings.py`
- Required vars: `AURA_EMAIL`, `AURA_PASSWORD`
- Optional vars with defaults: `AURA_LOCALE` (default: `en-US`), `AURA_APP_IDENTIFIER` (default: `com.pushd.client`), `AURA_DEVICE_IDENTIFIER` (default: `0000000000000000`)
- No `.env` file loader detected; vars must be set in shell environment

**Build:**
- No build config files present (`setup.py`, `pyproject.toml`, `Makefile` absent)

## Platform Requirements

**Development:**
- Python 3 with pip
- AWS credentials provisioned via Cognito Identity Pool (no static AWS keys required)
- Network access to `api.pushd.com`, `imgproxy.pushd.com`, AWS us-east-1 endpoints

**Production:**
- Not applicable; this is an offline/scripting tool intended for direct execution via `main.py`
- Entry point: `python main.py` (see `main.py`)

---

*Stack analysis: 2026-06-29*
