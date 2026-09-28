# Phase 16 Access-Mechanism Probes

Live probes for the album-access mechanism decision (`16-DECISION-RECORD.md`).
These are spike instruments: they prove or reject mechanisms with live
evidence, per the verdict rules locked in `16-CONTEXT.md` (D-03/D-04/D-05).

## Probes

| Probe | Mechanism | What it proves |
|---|---|---|
| `shared_link_probe.py` | Shared-album link (no auth) | Plain-HTTP fetch → `ds:1` parse → true item count vs the suspected ~500 ceiling; one `{baseUrl}=d` original hashed with the frame's base64-MD5 convention (16-03 fidelity input) |
| `browser_bootstrap.py` | Dedicated-profile browser + internal RPC | One-time interactive cookie harvest into the untracked 0600 vault; then a plain-`httpx` `batchexecute` album listing with no browser alive |
| `cookie_vault.py` | (support) | Storage + the **structural** sync/apply denylist — sync paths cannot read harvested cookies, by frame inspection, not convention |
| `common.py` | (support) | `redact_link()` (capability URLs never print/commit in full) + fail-loud raw fetch |

## Running

```bash
# Shared link — listing only (no auth, no cookies, no JS):
uv run python probes/shared_link_probe.py "$(cat probes/album-a.link)"

# Shared link — with one =d original download + base64-MD5:
uv run python probes/shared_link_probe.py "$(cat probes/album-a.link)" --download-n 1

# Browser — one-time harvest (interactive login in the opened window):
AURA_PROBE_CHROME_PROFILE=~/.config/auraframes/probes/chrome-profile \
  uv run python probes/browser_bootstrap.py bootstrap

# Browser — plain-httpx internal RPC listing (throwaway album):
uv run python probes/browser_bootstrap.py list --url "$(cat probes/throwaway.link)"
```

## Privacy rules (D-05, binding)

- **Full capability URLs never enter git.** They live only in untracked
  `probes/*.link` files or shell invocations. `probes/.gitignore` covers
  `*.link` and `.probe-downloads/`; `git check-ignore` proves it.
- Every URL printed by a probe goes through `redact_link()` — terminal
  scrollback carries the `AF1Qip…<last4>` shape only.
- Downloaded originals land in `.probe-downloads/` (gitignored) and are
  hashed with `auraframes.aws.s3client.get_md5` — the frame's own convention
  — never re-encoded.
- The cookie vault defaults to `~/.config/auraframes/probes/google-cookies.json`
  (outside the repo, 0600); `save()` refuses repo-inside paths outright.

## Survival promise (D-02)

`parse_af_initdata` from `shared_link_probe.py` is production-grade parser
code, not throwaway: if the shared-link mechanism is selected in
`16-DECISION-RECORD.md`, Phase 17 inherits this parser as the listing core
(and it survives even if the ceiling verdict rules the mechanism out — it is
the reference implementation either way).

## Verdict discipline (D-03/D-04)

A probe that cannot run is a **rejection verdict** ("bootstrap not
reproducible"), never an optimistic maybe. One documented retry after a
concrete fix is allowed; more is not. An unmeasurable ceiling is a bounded
risk with the lower bound recorded — the decision is taken anyway.
