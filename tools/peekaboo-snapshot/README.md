# peekaboo-snapshot

Production-grade data generator for the AI Peekaboo visibility dashboard.

This package fetches the latest analytics from the AI Peekaboo REST API and
writes a single compact JSON snapshot into one or more dashboard HTML files.
It replaces the legacy `generate_peekaboo_snapshot.py` single-file script with
a typed, testable Python package.

For deeper context see:

- [`../../docs/HANDOFF.md`](../../docs/HANDOFF.md)
- [`../../docs/API_CONTRACT.md`](../../docs/API_CONTRACT.md)

## Install

```bash
cd tools/peekaboo-snapshot
pip install -e ".[dev]"
```

`python-dotenv` is optional; install the `env` extra (or `dev`) to enable
automatic `.env` loading.

## Configure

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
```

Required environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `PEEKABOO_API_KEY` | yes | Read-only or read+write key (`pk_...`) |
| `PEEKABOO_BRAND_ID` | optional | Default brand UUID; override with `--brand-id` |

## Usage

Dry-run summary against the live API:

```bash
peekaboo-snapshot --brand-id <uuid> --dry-run
```

Inject into a dashboard:

```bash
peekaboo-snapshot \
  --brand-id <uuid> \
  --dashboard ~/Desktop/ai-monitoring-dashboard-v3.html \
  --dashboard /tmp/ai-visibility-dashboard/dashboard.html
```

Also save the snapshot JSON to disk:

```bash
peekaboo-snapshot --brand-id <uuid> --save snapshot.json
```

Filter the brand-selector dropdown (case-insensitive substring, repeatable):

```bash
peekaboo-snapshot --brand-id <uuid> --brand-filter peekaboo --brand-filter flexzo
```

Resume after an interruption: re-run the same command. Already-fetched prompt
details are loaded from `.peekaboo/checkpoint_<brand_id>.json`. Use
`--no-resume` to force a fresh run.

## Common flags

```
--time-range {7d,30d,90d}   History window (default 30d)
--brand-id ID               Brand UUID (overrides env)
--brand-filter NAME         Substring filter, repeatable
--dashboard PATH            Target HTML file, repeatable
--max-text-len N            Truncate response text (default 4000)
--dry-run                   Print summary, do not write
--save PATH                 Also write snapshot JSON to PATH
--no-resume                 Ignore checkpoint, refetch everything
-v, --verbose               DEBUG logging
```

## Develop

```bash
pip install -e ".[dev]"
pytest tests/ -q
ruff check src tests
mypy src
```

## Architecture

| Module | Responsibility |
|---|---|
| `cli.py` | Argparse, env loading, friendly error mapping |
| `config.py` | Frozen `Config` dataclass built from env + args |
| `client.py` | `requests.Session`, retries, rate limiting, typed endpoints |
| `models.py` | Pydantic v2 models for API and internal snapshot shapes |
| `aggregator.py` | Pure functions producing the dashboard-shaped snapshot |
| `injector.py` | Atomic snapshot injection between sentinel markers |
| `checkpoint.py` | Resume-from-checkpoint store for partial runs |
| `snapshot.py` | `SnapshotBuilder` orchestrator (`build()` + `run()`) |
| `logging_config.py` | Root logger formatter + level |

The injector deliberately does **not** patch any `AIM_INJECTED_DATA` block.
That responsibility is out of scope for this generator.
