# API Coverage — Google-facing production surfaces (Phase 17)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 17 integrates the mechanism the signed 16-DECISION-RECORD selected
> (browser-automation + shared-link bootstrap stage). The matrix records what the
> phase's production code touches, and what stays out with reasons.

| capability | decision | reason |
|---|---|---|
| shared-album page fetch + `AF_initDataCallback` parse (ds:1) | INTEGRATE | the bootstrap stage of the selected mechanism — batch-1 + share token/key extraction (D-06; live-proven 24/24 + 794/794) |
| internal `batchexecute` `snAcKc` continuation RPC | INTEGRATE | the selected mechanism's enumeration primitive (decision record); captured-and-replay method with `rpc_capture.py` as the redeploy-recovery instrument |
| `{baseUrl}=d` original download (+ 1-byte Range sizing) | INTEGRATE | fidelity MATCH proven (16-03); disk weight via Content-Range (live-proven); enumeration output needs per-item bytes |
| Google session via cookie vault (full jar, domain+path) | INTEGRATE | live-proven requirement (flattened dict reads as anonymous); vault boundary (denylist/0600/repo-refusal) carried intact |
| interactive cookie bootstrap (dedicated profile, system Chrome) | INTEGRATE | LGS-02's link command; bot-detection retry posture (channel=chrome + masked flags) carried |
| account album listing (for name-based selection) | INTEGRATE | D-05's name-or-link selection needs the account's shared-album names; served by the same logged-in session |
| Aura/Pushd Google-album-linking endpoints (Ambient) | OPT-OUT | abandoned 2026-09-28 (does not work in practice); not a reference |
| Picker API mediaItems (per-photo) | OPT-OUT | user-rejected: violates album granularity (LGS-04, Out of Scope) |
| Google Photos Library API | OPT-OUT | VERIFIED dead since 2025-03-31 — do not re-open |
| Takeout / Data Portability API / app-created albums | OPT-OUT | VERIFIED dead ends (v3.0 research) — do not re-open |
| Google OAuth (device flow / loopback) | OPT-OUT | not needed by the selected mechanism; cookie-expiry re-auth is the accepted path (LGS-02) |
| frame writes (upload/hide from album sync) | OPT-OUT | Phase 18's pipeline; this phase is read-only against the frame |
| multi-account (`--account`, per-account vaults) | OPT-OUT | D-04: mono-account now; Future (GSF) when a need is demonstrated |
| videos (`=dv`) | OPT-OUT | videos excluded from sync scope (carried replan decision); shape re-evaluated only if scope changes |
