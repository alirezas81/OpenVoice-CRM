# Security Policy

## Supported versions

Security fixes are developed against the latest version on the default branch. This early-stage project does not currently publish maintained release branches.

## Reporting a vulnerability

Please do not disclose exploitable vulnerabilities in a public issue or pull request. Use GitHub's private vulnerability reporting for this repository, if enabled. If private reporting is not available, contact the repository maintainers through GitHub and request a private channel.

Include the affected commit or version, impact, and steps to reproduce. Do not include customer records, credentials, call recordings, transcripts, or other sensitive data in a report. The maintainers will acknowledge reports as soon as practical and coordinate a fix and disclosure timeline with the reporter.

## Deployment security

- Keep API keys in environment variables or a dedicated secret manager; never commit `.env` files.
- Use least-privilege provider credentials and restrict access to the runtime host.
- Do not place secrets or real customer data in the sample knowledge base.
- Review provider data-processing, retention, and privacy terms before handling production conversations.
