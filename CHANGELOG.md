# Changelog

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
