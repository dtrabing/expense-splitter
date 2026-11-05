# Expense Splitter

[![CI](https://github.com/dtrabing/expense-splitter/actions/workflows/ci.yml/badge.svg)](https://github.com/dtrabing/expense-splitter/actions/workflows/ci.yml)

Paste what everyone paid. Get the fewest payments that settle the group.

**Live app:** https://expense-splitter-zeta-sooty.vercel.app

Built for the AI-assisted programming activity (DevOps: code, check in, test, deploy)
with Flask, pytest, GitHub Actions and Vercel.

## What it does

- **Input:** one expense per line (`name amount description`), plus an optional
  comma-separated list of everyone in the group so people who paid nothing still
  owe their share.
- **Process:** the total is split equally in integer cents (so balances always sum
  to exactly zero), then debts are settled greedily: the biggest debtor pays the
  biggest creditor until everyone is even. A group of *n* people never needs more
  than *n − 1* payments.
- **Output:** who pays whom, and each person's paid / fair share / balance.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/flask --app app run
```

Then open http://127.0.0.1:5000. Run the tests with:

```bash
.venv/bin/pytest -v
```

## JSON API

```bash
curl -s -X POST https://expense-splitter-zeta-sooty.vercel.app/api/split \
  -H 'Content-Type: application/json' \
  -d '{"expenses": "Alice 60 groceries\nBob 25.50 gas\nAlice 14.50 snacks",
       "participants": "Alice, Bob, Carol"}'
```

```json
{
  "total": "100.00",
  "people": [
    {"name": "Alice", "paid": "74.50", "share": "33.34", "balance": "41.16"},
    {"name": "Bob",   "paid": "25.50", "share": "33.33", "balance": "-7.83"},
    {"name": "Carol", "paid": "0.00",  "share": "33.33", "balance": "-33.33"}
  ],
  "transfers": [
    {"from": "Carol", "to": "Alice", "amount": "33.33"},
    {"from": "Bob",   "to": "Alice", "amount": "7.83"}
  ]
}
```

`expenses` may also be a list of objects: `{"payer": "Alice", "amount": 60, "description": "groceries"}`.
Bad input returns `400` with an `error` message that names the offending line.
`GET /api/health` returns `{"status": "ok"}`.

## The pipeline: code, check in, test, deploy

1. **Code.** `splitter/core.py` holds the pure logic; `app.py` is the Flask app
   (HTML form + JSON API); `tests/` covers both.
2. **Check in.** Work is pushed to `main` on GitHub.
3. **Test.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs `pytest`
   on Python 3.12 for every push to `main` and every pull request.
4. **Deploy.** Vercel's Flask preset serves `app.py` as a single function. The
   workflow's `deploy` job depends on the test job and only runs on `main`, so
   nothing untested ships. It deploys with the Vercel CLI when a `VERCEL_TOKEN`
   repository secret is present (no secrets live in the repo); without it the job
   logs a warning and skips, and the production deployment is made through
   Vercel's API with the commit SHA attached.

## Layout

```
app.py                  Flask routes (HTML form, /api/split, /api/health)
splitter/core.py        parsing, balances, settlement (no web code)
templates/index.html    the one page
tests/                  pytest suite
.github/workflows/      CI: test, then deploy
vercel.json             keeps tests out of the function bundle
```
