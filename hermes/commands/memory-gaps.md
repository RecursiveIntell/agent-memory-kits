# /memory-gaps

Detect knowledge gaps in your semantic memory store.

## Usage

```
/memory-gaps [--domain <domain>] [--namespace <ns>] [--top-k <N>]
```

## What it does

Calls the semantic-memory warm HTTP server and analyzes results for:
- **Structural gaps**: namespaces with very few facts
- **Content gaps**: shallow facts (very short content), missing graph edges
- **Low recall**: queries that return too few results
- **Low connectivity**: edge/fact ratio below 0.5

## Output

A `GapReportV1` JSON with per-gap severity (high/medium/low) and a summary count.

## Example

```
/memory-gaps --namespace hermes
```

Fails open (exit 0 with `server_available: false`) if the semantic-memory server is not running.