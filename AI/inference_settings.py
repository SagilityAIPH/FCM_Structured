"""Shared generation budget and truncation checks for PDF Reader entry points."""

DEFAULT_MAX_TOKENS = 32768
MAX_OUTPUT_TOKENS = 32768


def check_output_limit(stop_reason, max_tokens):
    """Reject incomplete answers before extraction can mark them as successful."""
    if stop_reason in {"max_tokens", "length"}:
        guidance = (
            f"Increase Output tokens to {MAX_OUTPUT_TOKENS:,} and retry."
            if max_tokens < MAX_OUTPUT_TOKENS
            else "The response still exceeds the configured budget; use a shorter document or review model settings."
        )
        raise RuntimeError(
            f"Bedrock reached the output token limit ({max_tokens:,}) before completing the answer. "
            "This budget can include model reasoning as well as the visible answer. "
            + guidance
        )
