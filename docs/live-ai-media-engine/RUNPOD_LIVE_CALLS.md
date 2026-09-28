# LiveShell cloud face and voice calls

## Product target

LiveShell provides one consent-gated live studio for face and voice transformation. A phone, tablet, or ordinary computer captures and plays media; a cloud GPU performs the transforms. The default output target is Full HD 1080p30 with 48 kHz audio; 720p30 is the explicit fallback when the measured worker or network cannot sustain the target. Seldrune must report actual decoded resolution, frame rate, audio sample rate, inference latency, end-to-end latency, and audio/video drift for each test session. GPU request profiles include RTX 4090, RTX PRO 4500 SE, RTX 5090, and RTX PRO 6000 Blackwell. Selecting a profile is only a scheduling request; the gateway must report the accelerator actually used, and quality claims require a measured GPU session receipt.

## GPU selection and runtime cost

**Pilot configuration:** use the existing RTX PRO 4500 SE pod for the first GPU smoke test and compare sustained 1080p30 with the RTX 4090. The pod's rate and exact device variant are account/host specific; verify the displayed price at launch and run `nvidia-smi` before recording device name or VRAM in a test receipt. NVIDIA lists 32 GB GDDR7 for the RTX PRO 4500 Blackwell workstation family, but do not assume the account's SE variant matches that configuration without checking.

Keep RTX 4090 as the performance-oriented live baseline: RunPod's public Secure Cloud listing is $0.74/hour for 24 GB. The RTX 5090 is $0.99/hour with 32 GB; use it only if measured 4090 results miss the latency gate. The RTX PRO 6000 is $2.09/hour with 96 GB; reserve it for concurrency or model-size needs demonstrated by profiling. These are published prices and can change. A 30-day always-on estimate at those rates is about $533/month for 4090, $713 for 5090, and $1,505 for PRO 6000, before storage. Verify current prices and GPU availability immediately before any run. See https://www.runpod.io/pricing.

Keep the media gateway available separately, route every active transformed call through the selected cloud GPU, and stop or scale down GPU workers after the last call. Pre-warm the worker before admitting a call; a warm minimum improves join time but incurs GPU charges while idle. If the product must keep one worker warm around the clock, budget its full hourly rate rather than treating GPU use as intermittent.

Do not treat VRAM or a GPU model name as evidence of output quality. Compare the 4500 SE and 4090 using the same authorized face/voice profiles and capture/network path. Keep 1080p30 only when decoded output sustains 30 fps, video inference p95 stays under one frame interval (33 ms), audio remains 48 kHz with real-time processing, end-to-end latency and A/V drift meet the release gates, and quality evaluators pass. Otherwise show the measured fallback instead of claiming HD readiness.

## Media route

1. The signed-in owner console checks organization permission and face/voice profile authorization. It records the user's explicit consent and keeps the AI-synthetic disclosure visible.
2. The trusted gateway issues a single-use session ticket bound to the organization, user, session, face profile, voice profile, consent states, disclosure state, and a maximum 15-minute lifetime. The browser or desktop companion never receives the long-lived worker token or ticket-signing secret.
3. The client uses WebRTC to the configured Seldrune media gateway. The gateway sends bounded, timestamped audio/video packets to the separate RunPod live worker over authenticated TLS TCP. RunPod's HTTP port 8000 remains for short control and uploaded-video jobs; it is not the live media stream.
4. The GPU worker checks each packet against the ticket, applies the face or voice profile, preserves timestamps, and returns transformed media. Every returned video frame must carry the persistent `AI-SYNTHETIC` mark. The browser studio also keeps its on-screen disclosure visible.
5. The Seldrune gateway returns the tracks to the Live Room or the desktop companion. Stop, disconnect, ticket expiry, and worker restart close the session and discard queued stale media.

## Implemented in this change

- A bounded JSON-header/binary-payload TCP framing contract for audio and video.
- HMAC-signed, single-use session tickets with organization, user, session, and profile bindings; explicit consent and synthetic-disclosure claims; and a 15-minute lifetime cap.
- TLS-only server startup, constant-time worker-token checking, monotonic per-track sequence checks, HD video and 48 kHz audio metadata checks, bounded in-flight work, and a multiplexed worker client.
- A dedicated RunPod worker entrypoint that refuses to start without TLS files, strong service/ticket secrets, and async face, voice, and labeling adapters.
- An injected face transform, injected voice transform, and required video-label callback. Missing model adapters cannot be presented as a successful transform.
- Unit coverage for packet limits, ticket expiry/signature/consent, profile binding, output labeling, audio/video round trips, and the TLS startup requirement.
- A strict production quality contract: the face adapter must return decoded HD dimensions, 30 fps windowed identity/temporal/blend metrics, and p95 inference evidence; the voice adapter must return decoded 48 kHz windowed speaker/content/naturalness, clipping/dropout, and p95 processing evidence.
- The production entrypoint requires explicit evaluator-calibrated pass thresholds in `SELDRUNE_LIVE_REALISM_POLICY_JSON`. It rejects byte-only adapters, missing evidence, evidence below threshold, and per-request latency over budget. The worker client carries measured evidence with each result.
- The strict live worker checks paired audio/video timestamps against the configured drift limit before inference and returns paired sync evidence with quality reports. `AVSyncState.validate_realism` is available to the gateway for client-side output measurements.

This bridge is a transport foundation. It does not install or train a face or voice model, connect the production LiveShell gateway to the RunPod listener, configure TURN, or prove a real phone/desktop call. The existing RTX 4090 uploaded-video worker and its port configuration remain unchanged. No GPU output or HD quality claim is made by unit tests. Perceptual thresholds must be calibrated on rights-cleared, consented evaluation samples for the selected model and evaluator; this example shows configuration shape, not validated performance:
```json
{"face_min_identity_similarity":0.82,"face_min_temporal_consistency":0.85,"face_min_blend_quality":0.80,"voice_min_speaker_similarity":0.82,"voice_min_content_preservation":0.90,"voice_min_naturalness":0.75,"voice_max_clipped_fraction":0.001,"voice_max_dropout_fraction":0.001,"max_processing_p95_ms":150.0,"max_av_drift_ms":80.0}
```
Use `FaceTransformOutput` and `VoiceTransformOutput` from `services.live_media.realism_quality_gate`; each result contains final decoded output bytes and a versioned evaluator report. No quality score is inferred from a model name, training loss, or successful transport.


The dedicated live worker entrypoint is `python -m services.live_media.runpod_live_worker`. Configure `SELDRUNE_LIVE_WORKER_TOKEN`, `SELDRUNE_LIVE_TICKET_SECRET`, `SELDRUNE_LIVE_REALISM_POLICY_JSON`, `SELDRUNE_LIVE_TLS_CERT`, `SELDRUNE_LIVE_TLS_KEY`, `SELDRUNE_FACE_TRANSFORM_ADAPTER`, `SELDRUNE_VOICE_TRANSFORM_ADAPTER`, and `SELDRUNE_SYNTHETIC_VIDEO_LABELER` on the separate worker. Adapter settings use `package.module:async_callable`; model packages and weights must be provided by the deployment image or mounted runtime. The listener defaults to TCP port `8765`, one active session, and two in-flight packets. These settings are separate from the existing uploaded-video service on port `8000`.

## Required next integrations

- Configure a distinct RunPod image and direct TCP port for the live worker; keep HTTP port 8000 and the current batch worker intact.
- Connect the Seldrune gateway's verified session lifecycle to ticket issuance, one session-scoped worker client, and the existing `LivePipeline`/`WorkerPool` interfaces.
- Load rights-cleared, authorized face and voice model adapters; fail readiness unless both adapters and the synthetic-video labeler are present.
- Configure authenticated TURN credentials for clients whose networks cannot establish a direct WebRTC path.
- Build the desktop companion's virtual camera and microphone path and validate the normal Teams/Zoom device selectors. Keep phone support in the browser Live Room unless a native mobile companion is built.
- Measure sustained 720p30 and 1080p30 face output, 48 kHz voice output, p50/p95 inference and glass-to-glass latency, audio/video drift, reconnect behavior, and GPU utilization using a real authorized camera and voice profile.

## Release gates

- Reject expired, replayed, cross-organization, cross-user, wrong-profile, or incomplete-consent tickets.
- Keep face and voice input/output in encrypted transport and avoid writing raw media or secrets to logs.
- Keep frame/audio queues bounded; drop stale video rather than accumulating latency.
- Show a clear stop action and release camera, microphone, and worker resources after stop or disconnect.
- Verify the `AI-SYNTHETIC` mark in the returned video frames, not only in a local UI overlay.
- Claim realistic HD readiness only after a real GPU-backed session passes the configured face and voice evidence gates and produces a signed receipt with returned frames, returned audio, decoded resolution/frame rate/sample rate, evaluator versions and scores, p95 latency, and paired A/V drift.
