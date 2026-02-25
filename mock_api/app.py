"""Flask mock API server for simulating external transaction data."""

import logging
from datetime import datetime, timedelta
from random import Random
from typing import Any

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)

app = Flask(__name__)

_SEED = 42
_rng = Random(_SEED)

_CATEGORIES = ["electronics", "clothing", "food", "books", "services"]


def _generate_transactions(count: int = 500) -> list[dict[str, Any]]:
    """Generate deterministic mock transaction data.

    Args:
        count: Number of transactions to generate.

    Returns:
        List of transaction dictionaries.
    """
    base_date = datetime(2024, 1, 1)
    transactions = []
    rng = Random(_SEED)

    for i in range(1, count + 1):
        transactions.append(
            {
                "transaction_id": i,
                "customer_id": rng.randint(1, 100),
                "amount": round(rng.uniform(5.0, 500.0), 2),
                "transaction_date": (
                    base_date + timedelta(hours=rng.randint(0, 8760))
                ).isoformat(),
                "category": rng.choice(_CATEGORIES),
            }
        )
    return transactions


_TRANSACTIONS = _generate_transactions()


@app.route("/api/transactions", methods=["GET"])
def get_transactions() -> tuple:
    """Return paginated transaction data with optional date filtering.

    Query Parameters:
        page: Page number (default 1).
        page_size: Items per page (default 100).
        since: ISO timestamp to filter transactions after this date.

    Returns:
        JSON response with transaction data and pagination metadata.
    """
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 100, type=int)
    since = request.args.get("since")

    data = _TRANSACTIONS
    if since:
        data = [t for t in data if t["transaction_date"] > since]

    total = len(data)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = data[start:end]

    return jsonify(
        {
            "data": page_data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }
    )


@app.route("/api/health", methods=["GET"])
def health_check() -> tuple:
    """Return API health status.

    Returns:
        JSON health status response.
    """
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
