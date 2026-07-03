---
name: llm-output-parsing
description: "Use semantic-memory-mcp LLM output parser tools to robustly parse JSON, string lists, choices, and numbers from raw LLM output without an additional LLM call. Handles think blocks, markdown fences, and malformed JSON."
---

# LLM Output Parsing

Use the sm_parse_* and sm_repair_json tools when you need to extract structured data from raw LLM output that may contain think blocks, markdown fences, trailing text, or malformed JSON.

## Tools

- `sm_parse_json` — extract typed JSON from raw LLM output. Handles think blocks, markdown fences, trailing text, and common JSON errors.
- `sm_parse_json_value` — extract untyped JSON (serde_json::Value). Use when the expected schema is unknown.
- `sm_repair_json` — attempt to repair common LLM JSON errors: trailing commas, unquoted keys, single quotes, missing brackets.
- `sm_strip_think_tags` — remove </think> blocks from text. Use when chain-of-thought reasoning leaks into output.
- `sm_parse_string_list` — extract a cleaned string list from raw LLM output. Handles bullet lists, numbered lists, comma-separated values, and JSON arrays.
- `sm_parse_choice` — extract a choice from raw LLM output given a list of valid options. Handles extra text, casing differences, and partial matches.
- `sm_parse_number` — extract a numeric value from raw LLM output. Handles text like "The answer is 42" or "Score: 0.85".

## When to use

- When parsing LLM output that may contain `<think>` blocks (chain-of-thought models)
- When LLM output wraps JSON in markdown fences (```json ... ```)
- When LLM output has trailing text after the JSON payload
- When LLM output has common JSON errors (trailing commas, single quotes, unquoted keys)
- When extracting a choice or number from verbose LLM text

## Rules

1. These tools are deterministic and local. No additional LLM call is needed.
2. Always try `sm_parse_json` first. If it fails, try `sm_repair_json` then `sm_parse_json` again.
3. Use `sm_strip_think_tags` before parsing if you know the model emits think blocks.
4. These tools complement semantic-memory search, not replace it. Use sm_search for recall, sm_parse_json for output parsing.
