# Research engine 2.6.0 / 研究引擎

This optional server source preserves the original six diagnostic tools and adds linked outcome feedback and a local retry tool. The standard skill package can run without hosting this service. `search_cases` uses the existing public teaching reference files; private research submissions are never appended to that collection.

Use Python 3.11+ and install `requirements.txt`. `server.py` is the stdio entrypoint; `http_server.py` provides `/mcp`, `/health`, `/case-report`, `/case-report/schema` and the authenticated `/case-report/list` and `/case-report/status`.

Production settings: `HOST=127.0.0.1` behind an HTTPS reverse proxy, `ZMXX_SERVER_MODE=remote`, a private `ZMXX_CASE_DB` path outside web/static roots, and a newly generated secret `ZMXX_CASE_READ_TOKEN` of at least 32 characters. Set `ZMXX_PUBLIC_BASE_URL` only when report artifacts are actually served there. Never commit these settings or put administrator credentials in skill packages.

Each accepted record now creates a private notification inbox entry in the same transaction. Email is optional and disabled by default. To enable future record alerts, set `ZMXX_NOTIFY_EMAIL_ENABLED=1` and `ZMXX_SMTP_HOST`, `ZMXX_SMTP_PORT`, `ZMXX_SMTP_SECURITY` (`ssl` or `starttls`), `ZMXX_SMTP_USER`, `ZMXX_SMTP_PASSWORD`, `ZMXX_SMTP_FROM`, and `ZMXX_SMTP_TO` in the service's private environment file. Run `python research_notifications.py worker` as a separate supervised process with the same environment. Existing records migrate to `inbox_only`; they do not send historical alerts. `/health` reports worker readiness; authenticated `/case-report/status` exposes counts and delivery failures. Tests use isolated databases and mocked SMTP.

For a local stdio client that should send authorized, deidentified cases to the operator, configure `ZMXX_RESEARCH_ENDPOINT=https://www.zmxx.work/case-report`. Its private pending queue remains local; remote tools cannot read that queue or retrieve another caller's case capability.

Read [RESEARCH_CASES_V3.md](RESEARCH_CASES_V3.md) for schema, access, migration, retention and recovery. Run `python -m pytest -q engine/tests` from the repository root after installing pytest and httpx in an isolated environment. Test fixtures are synthetic and never demonstrate real customer results.

本服务端源码随项目按 MIT License 发布；部署配置、研究库、历史原始记录、私有回执和访问密钥不属于本仓库发布材料，也不因源码采用 MIT 而公开。官网反馈表单源码位于 `web/`，可由同域静态服务提供，向同域 `/case-report` 提交。`case_token` 是每个案例独立的后续写入凭据，只在私有回执中保存，服务端仅存哈希。
