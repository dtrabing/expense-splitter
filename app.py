"""Expense Splitter: a small Flask app that settles shared expenses.

The module-level ``app`` is what ``flask run`` and Vercel's Flask preset load.
"""

from flask import Flask, jsonify, render_template, request

from splitter import (
    SplitError,
    expenses_from_records,
    parse_expenses,
    parse_participants,
    split_expenses,
)

SAMPLE_EXPENSES = """# name amount description
Alice 60 groceries
Bob 25.50 gas
Alice 14.50 snacks
"""
SAMPLE_PARTICIPANTS = "Alice, Bob, Carol"


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            expenses_text=SAMPLE_EXPENSES,
            participants_text=SAMPLE_PARTICIPANTS,
            result=None,
            error=None,
        )

    @app.post("/")
    def split_form():
        expenses_text = request.form.get("expenses", "")
        participants_text = request.form.get("participants", "")
        result, error, status = None, None, 200
        try:
            result = split_expenses(
                parse_expenses(expenses_text), parse_participants(participants_text)
            )
        except SplitError as exc:
            error, status = str(exc), 400
        return (
            render_template(
                "index.html",
                expenses_text=expenses_text,
                participants_text=participants_text,
                result=result,
                error=error,
            ),
            status,
        )

    @app.post("/api/split")
    def split_api():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="send a JSON object with an 'expenses' field"), 400
        try:
            raw = payload.get("expenses", [])
            expenses = parse_expenses(raw) if isinstance(raw, str) else expenses_from_records(raw)
            result = split_expenses(expenses, parse_participants(payload.get("participants")))
        except SplitError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(result)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()
