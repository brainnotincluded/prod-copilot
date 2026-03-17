#!/usr/bin/env python3
"""ML Evaluation Script for Prod Copilot orchestration quality.

Loads a test dataset and evaluates the MLOps orchestration pipeline
against expected intents, step actions, endpoints, and result types.

Modes:
    --mock  Validates dataset structure and returns deterministic baseline
            results without calling any external service (suitable for CI).
    --live  Calls the running MLOps /api/orchestrate endpoint and compares
            actual responses against expectations.

Results are printed as a summary table and saved to eval/results.json.
"""

import json
import argparse
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_dataset(path: str = "dataset.json") -> list[dict]:
    """Load evaluation dataset from a JSON file.

    Args:
        path: Path to the dataset JSON file (absolute or relative).

    Returns:
        List of test-case dicts.

    Raises:
        SystemExit: If the file is missing or unparseable.
    """
    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = Path(__file__).resolve().parent / filepath

    if not filepath.exists():
        print(f"ERROR: Dataset file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if not isinstance(dataset, list) or len(dataset) == 0:
        print("ERROR: Dataset must be a non-empty JSON array.", file=sys.stderr)
        sys.exit(1)

    # Validate required fields
    required_fields = {
        "query", "expected_intent", "expected_steps",
        "expected_endpoints", "expected_result_type", "difficulty", "tags",
    }
    for i, case in enumerate(dataset):
        missing = required_fields - set(case.keys())
        if missing:
            print(
                f"ERROR: Test case {i} is missing fields: {missing}",
                file=sys.stderr,
            )
            sys.exit(1)

    return dataset


# ---------------------------------------------------------------------------
# Mock evaluation
# ---------------------------------------------------------------------------

_GREETING_QUERIES = {"hi", "hello", "hey", "привет"}

_MOCK_INTENT_RULES: list[tuple[Any, str]] = [
    # Callable rules checked in order; first match wins.
]


def _mock_classify(query: str) -> str:
    """Heuristic intent classification for mock mode."""
    normalized = query.strip().lower().rstrip("!?./)")

    if not normalized:
        return "chat"
    if normalized in _GREETING_QUERIES:
        return "chat"

    # Greeting-like phrases (starts with a greeting word)
    greeting_starts = ("hi ", "hi,", "hello ", "hello,", "hey ", "hey,", "привет ", "привет,", "здравствуй")
    for g in greeting_starts:
        if normalized.startswith(g):
            return "chat"

    # Follow-up patterns (Russian + English)
    follow_up_markers = [
        "а их", "покажи подробнее", "а почему", "расскажи ещё",
        "из списка", "тот же", "а если",
    ]
    for marker in follow_up_markers:
        if marker in normalized:
            return "chat"

    # Unsupported / out-of-domain actions
    out_of_domain = ["deploy", "restart", "ssh", "docker", "kubectl"]
    for term in out_of_domain:
        if term in normalized:
            return "chat"

    # Default: anything mentioning data terms is api_query
    api_keywords = [
        "segment", "campaign", "audience", "kpi", "analytics",
        "user", "push", "template", "forecast", "performance",
        "show", "list", "get", "find", "filter", "compare",
        "покажи", "сегмент", "кампани", "аудитор", "пользовател",
        "шаблон", "уведомлен", "статистик",
    ]
    for kw in api_keywords:
        if kw in normalized:
            return "api_query"

    return "api_query"


def _mock_steps(case: dict) -> list[str]:
    """Return plausible step actions for mock mode.

    For greetings/chat returns ["chat_response"].
    For api_query returns the expected steps (simulating a correct planner).
    """
    intent = _mock_classify(case["query"])
    if intent == "chat":
        if not case["query"].strip():
            return []
        return ["chat_response"]
    return list(case["expected_steps"])


def _mock_result_type(case: dict) -> str:
    """Return the result type the mock would produce."""
    return case["expected_result_type"]


def evaluate_mock(dataset: list[dict]) -> list[dict]:
    """Mock evaluation -- validates dataset structure and returns baseline.

    Uses simple heuristics to simulate intent classification and step
    planning.  No LLM or network calls are made.

    Returns:
        List of per-case result dicts.
    """
    results: list[dict] = []
    for i, case in enumerate(dataset):
        query = case["query"]
        start = time.monotonic()

        actual_intent = _mock_classify(query)
        actual_steps = _mock_steps(case)
        actual_result_type = _mock_result_type(case)

        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        results.append({
            "index": i,
            "query": query[:80],
            "difficulty": case["difficulty"],
            "tags": case["tags"],
            "expected_intent": case["expected_intent"],
            "actual_intent": actual_intent,
            "intent_match": actual_intent == case["expected_intent"],
            "expected_steps": case["expected_steps"],
            "actual_steps": actual_steps,
            "steps_match": set(actual_steps) == set(case["expected_steps"]),
            "expected_result_type": case["expected_result_type"],
            "actual_result_type": actual_result_type,
            "result_type_match": actual_result_type == case["expected_result_type"],
            "elapsed_ms": elapsed_ms,
            "error": None,
        })

    return results


# ---------------------------------------------------------------------------
# Live evaluation
# ---------------------------------------------------------------------------

def evaluate_live(dataset: list[dict], base_url: str = "http://localhost:8001") -> list[dict]:
    """Live evaluation against running MLOps service.

    Sends each test query to POST /api/orchestrate and compares the
    response against expected values.

    Args:
        dataset: List of test cases.
        base_url: MLOps service base URL.

    Returns:
        List of per-case result dicts.
    """
    try:
        import httpx
    except ImportError:
        print(
            "ERROR: httpx is required for live evaluation. "
            "Install it with: pip install httpx",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"{base_url.rstrip('/')}/api/orchestrate"
    results: list[dict] = []

    # Sample endpoints payload representing the marketing API.
    # In a real setup these would come from the database / RAG index;
    # here we provide a minimal set so the planner has something to work with.
    sample_endpoints = [
        {"method": "GET", "path": "/api/segments", "summary": "List all audience segments"},
        {"method": "GET", "path": "/api/segments/{segment_id}", "summary": "Get segment details"},
        {"method": "POST", "path": "/api/segments", "summary": "Create a new audience segment"},
        {"method": "GET", "path": "/api/segments/search", "summary": "Search segments by name or description"},
        {"method": "GET", "path": "/api/segments/{segment_id}/audience", "summary": "Get audience size estimate"},
        {"method": "GET", "path": "/api/audiences", "summary": "List all audiences"},
        {"method": "POST", "path": "/api/audiences", "summary": "Create an audience from a segment"},
        {"method": "GET", "path": "/api/audiences/{audience_id}", "summary": "Get audience details"},
        {"method": "GET", "path": "/api/audiences/{audience_id}/overlap", "summary": "Calculate audience overlap"},
        {"method": "GET", "path": "/api/campaigns", "summary": "List all campaigns"},
        {"method": "POST", "path": "/api/campaigns", "summary": "Create a new campaign draft"},
        {"method": "GET", "path": "/api/campaigns/{campaign_id}", "summary": "Get campaign details with KPIs"},
        {"method": "GET", "path": "/api/campaigns/{campaign_id}/variants", "summary": "Get A/B test variant results"},
        {"method": "PATCH", "path": "/api/campaigns/{campaign_id}", "summary": "Update campaign status"},
        {"method": "POST", "path": "/api/push/generate", "summary": "Generate push notification variants"},
        {"method": "GET", "path": "/api/push/templates", "summary": "List push notification templates"},
        {"method": "GET", "path": "/api/analytics/kpi", "summary": "Get overall marketing KPIs"},
        {"method": "GET", "path": "/api/analytics/segments/{segment_id}/kpi", "summary": "Get segment-specific KPIs"},
        {"method": "GET", "path": "/api/analytics/audience-forecast", "summary": "Forecast audience size"},
        {"method": "GET", "path": "/api/analytics/campaign/{campaign_id}/performance", "summary": "Campaign performance metrics"},
        {"method": "GET", "path": "/api/users", "summary": "List users with filtering"},
        {"method": "GET", "path": "/api/users/stats", "summary": "Get user statistics breakdown"},
        {"method": "GET", "path": "/api/users/{user_id}", "summary": "Get user profile"},
    ]

    with httpx.Client(timeout=60.0) as client:
        for i, case in enumerate(dataset):
            query = case["query"]
            print(f"  [{i + 1}/{len(dataset)}] {query[:60]}...", flush=True)

            start = time.monotonic()
            error = None
            actual_intent = "unknown"
            actual_steps: list[str] = []
            actual_result_type = "unknown"

            # Skip empty queries -- the endpoint rejects them with 422
            if not query.strip():
                elapsed_ms = 0.0
                actual_intent = "chat"
                actual_steps = []
                actual_result_type = "text"
            else:
                try:
                    payload = {
                        "query": query,
                        "endpoints": sample_endpoints,
                    }
                    resp = client.post(url, json=payload)
                    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

                    if resp.status_code == 200:
                        body = resp.json()
                        actual_result_type = body.get("type", "unknown")

                        # Infer intent from the response
                        metadata = body.get("metadata") or {}
                        if metadata.get("mode") == "chat":
                            actual_intent = "chat"
                            actual_steps = ["chat_response"]
                        else:
                            actual_intent = "api_query"
                            # Extract step actions from metadata if available
                            steps_data = metadata.get("steps") or metadata.get("plan") or []
                            if isinstance(steps_data, list):
                                actual_steps = [
                                    s.get("action", "unknown")
                                    for s in steps_data
                                    if isinstance(s, dict)
                                ]
                            # Fallback: if no step info in metadata, infer from result
                            if not actual_steps:
                                actual_steps = _infer_steps_from_result(body)
                    elif resp.status_code == 422:
                        # Validation error (e.g. empty query)
                        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                        actual_intent = "chat"
                        actual_steps = []
                        actual_result_type = "text"
                        error = f"HTTP 422: {resp.text[:200]}"
                    else:
                        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                        error = f"HTTP {resp.status_code}: {resp.text[:200]}"

                except httpx.ConnectError:
                    elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                    error = f"Connection refused at {base_url}"
                except Exception as exc:
                    elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                    error = str(exc)

            results.append({
                "index": i,
                "query": query[:80],
                "difficulty": case["difficulty"],
                "tags": case["tags"],
                "expected_intent": case["expected_intent"],
                "actual_intent": actual_intent,
                "intent_match": actual_intent == case["expected_intent"],
                "expected_steps": case["expected_steps"],
                "actual_steps": actual_steps,
                "steps_match": set(actual_steps) == set(case["expected_steps"]),
                "expected_result_type": case["expected_result_type"],
                "actual_result_type": actual_result_type,
                "result_type_match": actual_result_type == case["expected_result_type"],
                "elapsed_ms": elapsed_ms,
                "error": error,
            })

    return results


def _infer_steps_from_result(body: dict) -> list[str]:
    """Best-effort step inference when metadata lacks explicit step info."""
    result_type = body.get("type", "text")
    data = body.get("data") or {}

    # If data has "content" and type is "text", likely a direct response
    if result_type == "text" and "content" in data:
        return ["format_output"]

    # If data looks like table/list data, assume api_call + format_output
    if result_type in ("table", "list", "chart", "dashboard"):
        return ["api_call", "format_output"]

    return ["format_output"]


# ---------------------------------------------------------------------------
# Metrics calculation
# ---------------------------------------------------------------------------

def calculate_metrics(results: list[dict]) -> dict:
    """Calculate aggregate evaluation metrics from per-case results.

    Returns:
        Dict with overall and per-difficulty/tag breakdowns.
    """
    total = len(results)
    if total == 0:
        return {"error": "No results to evaluate"}

    # Overall metrics
    intent_correct = sum(1 for r in results if r["intent_match"])
    steps_correct = sum(1 for r in results if r["steps_match"])
    result_type_correct = sum(1 for r in results if r["result_type_match"])
    all_correct = sum(
        1 for r in results
        if r["intent_match"] and r["steps_match"] and r["result_type_match"]
    )
    errors = sum(1 for r in results if r["error"] is not None)

    avg_latency = (
        round(sum(r["elapsed_ms"] for r in results) / total, 2)
        if total > 0 else 0.0
    )

    metrics: dict[str, Any] = {
        "total_cases": total,
        "intent_accuracy": round(intent_correct / total * 100, 1),
        "step_match_rate": round(steps_correct / total * 100, 1),
        "result_type_accuracy": round(result_type_correct / total * 100, 1),
        "overall_pass_rate": round(all_correct / total * 100, 1),
        "error_count": errors,
        "avg_latency_ms": avg_latency,
    }

    # Per-difficulty breakdown
    by_difficulty: dict[str, dict] = {}
    for diff in ("easy", "medium", "hard"):
        subset = [r for r in results if r["difficulty"] == diff]
        if not subset:
            continue
        n = len(subset)
        by_difficulty[diff] = {
            "count": n,
            "intent_accuracy": round(
                sum(1 for r in subset if r["intent_match"]) / n * 100, 1
            ),
            "step_match_rate": round(
                sum(1 for r in subset if r["steps_match"]) / n * 100, 1
            ),
            "result_type_accuracy": round(
                sum(1 for r in subset if r["result_type_match"]) / n * 100, 1
            ),
            "pass_rate": round(
                sum(
                    1 for r in subset
                    if r["intent_match"] and r["steps_match"] and r["result_type_match"]
                ) / n * 100, 1
            ),
        }
    metrics["by_difficulty"] = by_difficulty

    # Per-tag breakdown
    all_tags: set[str] = set()
    for r in results:
        all_tags.update(r.get("tags") or [])

    by_tag: dict[str, dict] = {}
    for tag in sorted(all_tags):
        subset = [r for r in results if tag in (r.get("tags") or [])]
        if not subset:
            continue
        n = len(subset)
        by_tag[tag] = {
            "count": n,
            "intent_accuracy": round(
                sum(1 for r in subset if r["intent_match"]) / n * 100, 1
            ),
            "pass_rate": round(
                sum(
                    1 for r in subset
                    if r["intent_match"] and r["steps_match"] and r["result_type_match"]
                ) / n * 100, 1
            ),
        }
    metrics["by_tag"] = by_tag

    return metrics


# ---------------------------------------------------------------------------
# Summary display
# ---------------------------------------------------------------------------

def print_summary(metrics: dict, results: list[dict]) -> None:
    """Print a formatted summary table to stdout."""
    sep = "=" * 72
    thin_sep = "-" * 72

    print(f"\n{sep}")
    print("  PROD COPILOT EVALUATION RESULTS")
    print(sep)

    print(f"\n  Total test cases:       {metrics['total_cases']}")
    print(f"  Intent accuracy:        {metrics['intent_accuracy']}%")
    print(f"  Step match rate:        {metrics['step_match_rate']}%")
    print(f"  Result type accuracy:   {metrics['result_type_accuracy']}%")
    print(f"  Overall pass rate:      {metrics['overall_pass_rate']}%")
    print(f"  Errors:                 {metrics['error_count']}")
    print(f"  Avg latency:            {metrics['avg_latency_ms']} ms")

    # Difficulty breakdown
    by_diff = metrics.get("by_difficulty", {})
    if by_diff:
        print(f"\n{thin_sep}")
        print("  BREAKDOWN BY DIFFICULTY")
        print(thin_sep)
        print(f"  {'Difficulty':<12} {'Count':>6} {'Intent':>8} {'Steps':>8} {'Type':>8} {'Pass':>8}")
        print(f"  {'-' * 12} {'-' * 6} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8}")
        for diff in ("easy", "medium", "hard"):
            if diff not in by_diff:
                continue
            d = by_diff[diff]
            print(
                f"  {diff:<12} {d['count']:>6} "
                f"{d['intent_accuracy']:>7.1f}% "
                f"{d['step_match_rate']:>7.1f}% "
                f"{d['result_type_accuracy']:>7.1f}% "
                f"{d['pass_rate']:>7.1f}%"
            )

    # Tag breakdown
    by_tag = metrics.get("by_tag", {})
    if by_tag:
        print(f"\n{thin_sep}")
        print("  BREAKDOWN BY TAG")
        print(thin_sep)
        print(f"  {'Tag':<16} {'Count':>6} {'Intent':>8} {'Pass':>8}")
        print(f"  {'-' * 16} {'-' * 6} {'-' * 8} {'-' * 8}")
        for tag, d in by_tag.items():
            print(
                f"  {tag:<16} {d['count']:>6} "
                f"{d['intent_accuracy']:>7.1f}% "
                f"{d['pass_rate']:>7.1f}%"
            )

    # Failures detail
    failures = [r for r in results if not (r["intent_match"] and r["steps_match"] and r["result_type_match"])]
    if failures:
        print(f"\n{thin_sep}")
        print(f"  FAILED CASES ({len(failures)})")
        print(thin_sep)
        for r in failures:
            query_preview = r["query"][:55]
            issues = []
            if not r["intent_match"]:
                issues.append(f"intent: {r['actual_intent']} != {r['expected_intent']}")
            if not r["steps_match"]:
                issues.append(f"steps: {r['actual_steps']} != {r['expected_steps']}")
            if not r["result_type_match"]:
                issues.append(f"type: {r['actual_result_type']} != {r['expected_result_type']}")
            if r["error"]:
                issues.append(f"error: {r['error'][:60]}")
            print(f"  [{r['index']:>2}] {query_preview}")
            for issue in issues:
                print(f"       -> {issue}")

    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(results: list[dict], metrics: dict, output_path: str) -> None:
    """Save evaluation results and metrics to a JSON file."""
    filepath = Path(output_path)
    if not filepath.is_absolute():
        filepath = Path(__file__).resolve().parent / filepath

    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": metrics,
        "results": results,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {filepath}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Prod Copilot orchestration quality against a test dataset.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run mock evaluation (no LLM, deterministic heuristics).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live evaluation against the MLOps service.",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Base URL of the MLOps service (default: http://localhost:8001).",
    )
    parser.add_argument(
        "--dataset",
        default="dataset.json",
        help="Path to the evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--output",
        default="results.json",
        help="Path to save evaluation results (default: results.json).",
    )
    args = parser.parse_args()

    if not args.mock and not args.live:
        print("ERROR: Specify --mock or --live mode.", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.mock and args.live:
        print("ERROR: Choose either --mock or --live, not both.", file=sys.stderr)
        sys.exit(1)

    # Load dataset
    print(f"Loading dataset from {args.dataset}...")
    dataset = load_dataset(args.dataset)
    print(f"Loaded {len(dataset)} test cases.\n")

    # Evaluate
    if args.mock:
        print("Running MOCK evaluation...")
        results = evaluate_mock(dataset)
    else:
        print(f"Running LIVE evaluation against {args.url}...")
        results = evaluate_live(dataset, base_url=args.url)

    # Calculate metrics & display
    metrics = calculate_metrics(results)
    print_summary(metrics, results)

    # Save
    save_results(results, metrics, args.output)


if __name__ == "__main__":
    main()
