# API Coverage — External album-access surfaces (Phase 16 probes)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 16 is decision-producing, not feature-producing: it PROBES two external
> surfaces with committed scripts but integrates none into production code.
> Production integration happens (or not) after the decision record selects the
> mechanism — the matrix below records what the probes touch, and the deferred
> capabilities that the selection implies.

| capability | decision | reason |
|---|---|---|
| shared-album page fetch (`photos.google.com/share/...`) | INTEGRATE | LGS-01 probe target — committed probe `probes/shared_link_probe.py` |
| `AF_initDataCallback` item parse | INTEGRATE | the enumeration primitive the probe (and Phase 17) needs |
| `{baseUrl}=d` original download | INTEGRATE | LGS-06 fidelity comparison requires downloading originals |
| shared-album lazy-load pagination RPC | OPT-OUT | research-confirmed no published prior art; ceiling becomes a bounded documented risk (D-04) — a pagination build would be Phase 17+ scope, gated by the decision record |
| Google login / cookie bootstrap (Chromium) | INTEGRATE | LGS-01 probe target — committed probe `probes/browser_bootstrap.py` |
| internal `batchexecute` album listing RPC | INTEGRATE | the browser mechanism's enumeration primitive; probed once end-to-end per LGS-01 |
| Aura/Pushd Google-album-linking endpoints (Ambient) | OPT-OUT | abandoned 2026-09-28 — Aura's server-side sync does not work in practice; not a reference for anything |
| Picker API mediaItems | OPT-OUT | user-rejected: per-photo picking violates album granularity (Out of Scope) |
| Google Photos Library API (`photoslibrary.*`) | OPT-OUT | VERIFIED dead since 2025-03-31 (v3.0 research) — do not re-open |
| app-created album read-back | OPT-OUT | VERIFIED dead end (v3.0 research §3) — do not re-open |
| Takeout / Data Portability API | OPT-OUT | VERIFIED dead ends (v3.0 research §2) — do not re-open |
| upload to Aura frame (select_asset/S3/batch_update) | OPT-OUT | not this phase: 16-03 reads the frame's md5_hash only; writes stay gated and belong to Phase 18's pipeline |
| Google OAuth (device flow / loopback) | OPT-OUT | not needed by either surviving mechanism; re-evaluated only if a future mechanism requires it (GSF-02) |
