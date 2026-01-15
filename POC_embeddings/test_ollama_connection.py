import argparse
import json
import sys

from helper import get_embeddings, test_ollama_connection


def main():
    parser = argparse.ArgumentParser(description="Test Ollama connectivity and embedding endpoint.")
    parser.add_argument(
        "--text",
        default="ping",
        help="Text to embed for the connectivity test request (default: 'ping').",
    )
    parser.add_argument(
        "--sample",
        action="append",
        dest="samples",
        help="Optional sample text to embed (can be passed multiple times).",
    )
    args = parser.parse_args()

    result = {}

    # 1) Connectivity check (tags + single embed)
    try:
        result["connection"] = test_ollama_connection(args.text)
    except Exception as exc:
        result["connection"] = {
            "ok": False,
            "errors": [f"unexpected_error: {exc}"],
        }

    # 2) Sample embeddings (if requested)
    samples = args.samples or []
    if samples:
        try:
            embeds = get_embeddings(samples)
            if embeds:
                sample_info = []
                for text, emb in zip(samples, embeds):
                    sample_info.append(
                        {
                            "text": text,
                            "embedding_len": len(emb),
                            "embedding_preview": emb[:5] if isinstance(emb, list) else None,
                        }
                    )
                result["sample_embeddings"] = {"ok": True, "items": sample_info}
            else:
                result["sample_embeddings"] = {"ok": False, "errors": ["embedding returned None"]}
        except Exception as exc:
            result["sample_embeddings"] = {"ok": False, "errors": [f"embedding_error: {exc}"]}

    # Overall exit code: fail if either connectivity or samples failed (when samples provided)
    exit_ok = result.get("connection", {}).get("ok", False)
    if samples:
        exit_ok = exit_ok and result.get("sample_embeddings", {}).get("ok", False)

    print(json.dumps(result, indent=2))
    sys.exit(0 if exit_ok else 1)


if __name__ == "__main__":
    main()
