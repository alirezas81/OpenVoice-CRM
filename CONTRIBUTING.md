# Contributing to OpenVoice-CRM

Thanks for your interest in improving OpenVoice-CRM! Contributions of all sizes are welcome, including bug reports, documentation, tests, accessibility improvements, language support, transport adapters, and integrations.

## Before you start

1. Search existing issues and pull requests to avoid duplicate work.
2. For a substantial feature or architectural change, open an issue first so we can discuss scope and design.
3. Never include API keys, customer data, call recordings, private transcripts, or other secrets in an issue, commit, fixture, or pull request.

## Development setup

OpenVoice-CRM currently targets Python 3.11 or newer (the selected Pipecat local-audio extras require Python 3.11+).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Set the required Anthropic and Groq keys in `.env` before running the live agent. You can compile-check the source without credentials:

```bash
python -m compileall -q src
```

## Contribution guidelines

- Keep changes focused and explain the user or maintainer benefit.
- Preserve the separation between audio transport, turn orchestration, retrieval, LLM provider, and TTS adapter.
- Make provider choices and model settings configurable; avoid embedding secrets or tenant-specific data in source.
- Keep customer-facing responses grounded in the configured knowledge base and avoid unsupported product/security promises.
- Add or update tests and documentation for behavior changes. If a change needs live audio or paid API credentials, explain that limitation in the PR.
- Use clear, descriptive commit messages and run `git diff --check` before submitting.
- Be respectful and constructive in reviews and discussions.

## Pull requests

A good pull request includes:

- A concise summary and motivation.
- Relevant implementation notes and configuration changes.
- Tests/checks performed and any known limitations.
- Screenshots, logs, or sample data only when they are safe to publish and contain no secrets or personal data.

By participating, you agree to follow the project's code of conduct and to license your contribution under the repository's MIT License.
