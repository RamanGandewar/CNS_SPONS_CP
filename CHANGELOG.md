# Changelog

## 2.0.0 - 2026-04-30

- Reworked authentication to JWT-based auth with role-aware access for `analyst`, `operator`, and `admin`.
- Added structured JSON logging with `request_id`, `job_id`, `user_id`, `duration_ms`, and verdict context.
- Added audit logging for signup, login, logout, analysis submission, and admin actions.
- Expanded health reporting to include DB status, Redis connectivity, Celery mode, uptime, and model count.
- Added Grafana and Prometheus monitoring assets under `monitoring/`.
- Added exportable forensic PDF reports for completed analyses.
- Added ensemble inference across both bundled TFLite models.
- Added forensic secondary signals: frequency-domain analysis, optical-flow consistency, facial landmark displacement fallback, and audio-visual sync proxy.
- Added model registry and calibration metadata files in `model/`.
- Added notebook-to-Python exports under `notebooks_converted/`.
- Added optional OpenTelemetry and Celery/Redis production hooks with thread-based fallback in local mode.

## 1.0.0 - 2026-04-28

- Added request-traced API responses with `request_id`.
- Added async job processing with `/api/v1/analyze`, `/api/v1/status/<job_id>`, and `/api/v1/result/<job_id>`.
- Added SQLite analysis history for observability and admin analytics.
- Added Prometheus-compatible `/metrics`.
- Added `/health` and `/api/v1/model/info`.
- Added input validation service for size, duration, MP4/MOV signature, and readable frames.
- Added security headers, CORS configuration, and rate limiting hooks.
- Added React admin analytics dashboard.
- Added model metadata registry file.
- Added GitHub Actions CI workflow.
