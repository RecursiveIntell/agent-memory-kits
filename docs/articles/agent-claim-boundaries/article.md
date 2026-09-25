# The agent said “done.”  What did the evidence actually prove?

**A source-pinned case study in command receipts, claim support, and release decisions**

Josh Stevenson, RecursiveIntell

Evidence cutoff: September 25, 2026

A passing command can tell me what happened when that command ran.  It cannot, by itself, tell me whether I ran the right commands, whether they covered the change, or whether the claim I want to make follows from their results.  That distinction sounds obvious until the evidence is wrapped in a polished packet with hashes and a green-looking disposition.

I maintain a small command-receipt script in `agent-memory-kits`.  For this article, I gave it a deliberately false test claim:

```text
Claim:   The entire test suite passed and the software is production ready
Command: true
```

The local script returned exit code `0` and a packet with `"disposition": "promote"`.  It also included a warning that command receipts prove only the listed gates ran, not untested behavior.  Both facts are true descriptions of what the code emitted.  The `true` command did not run a test suite, and no one should treat this fixture's claim as a statement about any actual release.  The mismatch is between an unrestricted claim string and a disposition computed solely from the exit status of caller-supplied commands.[6]

You do not have to take my summary on faith.  The exact source revision, raw packets, original process output, capture program, and local verifier are linked below.  The observations are **author-run local fixtures**, not independent reproduction, a formal security result, a customer incident, or evidence that an autonomous agent made this particular statement.

- [Captured process output and SHA-256 inventory](receipts/capture.json)
- [Broad claim plus passing `true`: raw packet](receipts/packets/broad-pass.json)
- [Narrower claim plus passing `true`: raw packet](receipts/packets/narrow-pass.json)
- [Broad claim plus failing `false`: raw packet](receipts/packets/broad-fail.json)
- [Capture and verification program](reproduce.py)

The point is not that agents are uniquely dishonest.  A human can overread a green check just as easily.  The point is that a receipt is an observation with a scope, while “done” is usually a bundle of claims about behavior, coverage, identity, and permission.  If we do not make those transitions explicit, the extra metadata can make an unsupported conclusion *look* more trustworthy.

## The three observations, not a benchmark

The fixture invokes the same public Python script in three disposable directories.  Its only shell commands are the literal `true` and `false`.  The capture sets `--no-memory`, does not set the optional ClaimLedger-write flag, and does not call an external model.  It records the script's output without editing the emitted packet bytes.  These precautions limit the experiment; they do **not** turn Python subprocess execution into a security sandbox or certify that an arbitrary version of the script has no other effects.

| Case | Supplied claim | Supplied command | Command exit | Script exit | Script disposition | What the reader may conclude |
| --- | --- | --- | ---: | ---: | --- | --- |
| [Broad passing claim](receipts/packets/broad-pass.json) | “The entire test suite passed and the software is production ready” | `true` | `0` | `0` | `promote` | The listed command exited successfully.  Nothing here shows that any suite ran or that the software is ready. |
| [Narrow passing claim](receipts/packets/narrow-pass.json) | “The supplied true command exited zero” | `true` | `0` | `0` | `promote` | The recorded command and exit status fit this much narrower observation.  The script still does not evaluate the English meaning of the claim. |
| [Broad failing claim](receipts/packets/broad-fail.json) | Same broad claim | `false` | `1` | `1` | `reject` | The supplied command failed, so the script rejects its own command-outcome gate.  This says nothing about which unrun tests would pass. |

The manifest contains the exact output bytes, SHA-256 digests of each copied packet, process exits, the Python version and OS family, and the pinned **source** Git commit plus source-file hash.  The [verifier](reproduce.py) checks those byte hashes, re-computes the script's own packet digest, verifies the expected case and command outcomes, and refuses a different source blob.  I also altered a *copy* of one packet's disposition during local validation; the verifier returned nonzero with `broad-pass: packet bytes changed`.  That tamper check verifies this package's integrity behavior, not the truth of the original claim.

The `true` command is useful here precisely because it is uninteresting.  If I had selected a plausible-looking test command, a reader might wonder whether the test happened to cover the claim.  `true` removes that ambiguity.  A single successful process exit is a fact; the leap from that fact to “the entire test suite passed” is visible without interpreting a test runner, a model, or a complicated trace.

## The mechanism in the source

This example is tied to `agent-memory-kits` commit `77f8b6829e5fc09460c70553413cd0bd5560a8be`, not to an unspecified current version.  The tracked source file's SHA-256 is `f2d0c8555b143fb770ca3b021549b8593697ea30ea9a3bdf59eef7fbc0aec5ea`.  At that revision, the operative rule is short:

```python
all_passed = all(row["exit_code"] == 0 and not row["timed_out"] for row in command_receipts)
disposition = "promote" if all_passed else "reject"
```

The claim string is stored in the packet, but this rule does not parse the claim or compare it with a declared set of required checks.  The packet then records both the disposition and this unusually candid boundary: “Command receipts prove the listed gates ran with the captured exit codes; they do not prove untested behavior.”  The warning is good.  The risk is that a downstream reader or automation treats `promote` as approval of the free-form claim despite that warning.  The observed mismatch is in the **meaning attached to the disposition**, not in the recorded process exit.[6]

The repository's focused unit tests passed in my local run: three tests, no failures.  One of those tests intentionally expects a `promote` packet for a “plugin gates pass” claim paired with `true`.  The tests establish that the current command-outcome rule works as coded.  They do not test whether a claim's words follow from the commands supplied.[7]  I am not calling this a discovered compromise, a production incident, or proof that every evidence tool has the same defect.

There is an important sibling distinction.  A later **Rust** Agent Evidence Workbench branch in the Libraries repository has a regression test requiring a broad caller claim paired with `true` to remain unsupported and the `prove` process to exit nonzero.  It also has tests for failed commands and untracked source-content drift.[9]  That branch is not the Python script used in this capture.  Conflating the two would turn a bounded example into a stale allegation against a different implementation.

## Four questions hiding inside “done”

I find it useful to separate four questions that often collapse into a single status field.

**1. Did an event happen?**  A process started with an identified command in an identified working directory and returned an exit code.  Capture the stdout and stderr or their digests, the time, timeout state, and the source snapshot.  This is the territory of an execution receipt.  Here, `true` did run and exited zero.

**2. Is the retained evidence complete for the declared question?**  If the question is “did all required tests run?”, I need an inventory of required tests or a committed evaluation manifest.  I also need explicit results for failed, skipped, timed-out, or missing entries.  An integrity hash over one retained `true` result does not tell me whether I omitted ninety-nine other checks.  ClaimReceipt makes this distinction particularly clear in its discussion of evidence sufficiency versus coverage for agent evaluations.[3]  Our three-case fixture does not implement ClaimReceipt or reproduce its published evaluation.

**3. Does that evidence support this particular sentence?**  “`true` exited zero” and “the entire test suite passed” differ even when the underlying process result is identical.  A digest can bind the bytes of the receipt; it does not supply the missing entailment.  If a tool cannot assess the semantic relation, the accurate machine output is “command observed; support for caller claim not adjudicated,” not an unrestricted approval.  A maintainer can then inspect the test definitions and make a bounded human judgment.

**4. Who is allowed to turn support into a decision?**  Even a well-supported test claim does not automatically authorize a merge, deployment, release, or public maturity statement.  A policy might require a named reviewer, source-to-build identity, CI at the exact commit, a license check, or a held-out evaluation.  Those conditions are not properties of a successful `true` command.  Release admission is a separate transition whose owner and missing evidence should be visible.

The questions have different failure modes.  A missing process result is an observation problem.  A missing test inventory is a coverage problem.  A claim that overstates its witness is a support problem.  A bot that merges without the required approval has crossed an authority boundary.  More trace detail can help diagnose each failure, but merely accumulating trace events cannot decide all four.

These states should not collapse into a boolean.  **Failed** means a check ran and reported failure.  **Skipped** means a check was identified but not exercised under its stated conditions.  **Not run** may mean no attempt occurred.  **Blocked** means a prerequisite prevented a valid attempt.  **Unknown** can mean the system never established which checks the claim required.  Each state asks for a different next action.  Retrying a failed command, setting up a missing dependency, and defining the relevant test set are not interchangeable repairs.  A green check elsewhere cannot erase any of them.

The same discipline applies to retries.  If the first attempt fails and the second passes, retain both observations with their source identities and conditions.  A hidden retry can make an intermittent failure vanish from the story without making the system more reliable.  If the source changed between attempts, there are two distinct candidate states; the later pass is not a retroactive correction of the first result.  A review packet should make the sequence inspectable rather than selecting whichever terminal line looks best.  This article's three cases are separate fixtures, not three attempts to repair one run, and the manifest lists all three.

A machine can enforce narrow transitions without being asked to understand every sentence.  It can reject a missing command result, verify hashes, require a source binding, or refuse release admission when an enumerated mandatory check is absent.  It can also say “not adjudicated” when no justified semantic rule connects a witness to a free-form claim.  That is not a weak outcome.  It is the accurate one when the alternative is manufacturing certainty from a process exit.

That distinction also keeps adjacent tooling in perspective.  LangSmith describes traces as collections of runs representing work such as model calls, retrieval, and tool invocations; its evaluation documentation describes curated examples, offline regressions, and online monitoring.[4][5]  Those are valuable inputs to review.  They do not, just by existing, certify every final English sentence an agent writes.  GitHub artifact attestations bind information about where and how a software artifact was built, which is another useful but different question from whether a broad behavioral claim is true.[8]  This is not an argument against tracing, evaluation, or attestations.  It is an argument for respecting what each witness actually witnesses.

## What a less misleading packet would say

For the broad fixture, I would separate command observation from claim support and release admission, rather than overload one `disposition`:

```text
Observed command:       true
Observed outcome:       exited 0
Claim:                  the entire test suite passed and the software is production ready
Claim support:          not established by this command
Required-test coverage: unknown; no suite inventory supplied
Release decision:       not made
Next check:             identify the required suite, run it at an exact source revision,
                        retain its results, then review the remaining release gates
```

This is an **illustrative review format**, not an output of the existing Python script or a new protocol I implemented for this article.  It leaves useful evidence intact without pretending that missing information has a favorable value.  In the narrow fixture, a reviewer can reasonably say the receipt supports the limited observation that the supplied `true` command exited zero.  That does not make the script a general natural-language claim judge.

A useful contract can be simple.  Every material public or release-facing sentence should identify its subject, revision, required witnesses, actual witnesses, known contrary evidence, and the rule or person allowed to decide.  When there is no declared requirement set, the honest coverage state is **unknown**, not “all required checks passed.”  When evidence supports only an operation, the honest claim state is **observed**, not “verified production-ready.”  This does not require a new top-level agent platform.  It can begin as a short review packet over existing Git, test, and CI artifacts.

### A practical review pass

Take a real coding-agent handoff that says, “I fixed the bug and all tests pass.”  Do not begin by asking the agent to summarize its own success more confidently.  Ask a sequence of narrower questions:

1. **Freeze the subject.**  Which repository, branch, commit, dirty files, generated files, and dependency state were in scope when the checks ran?  A later file edit makes an earlier green result historical evidence, not a current result.
2. **Split the sentence.**  “Fixed” is one claim about behavior.  “All tests pass” is a different claim about an enumerated test set.  “Safe to release” would be a third claim with its own requirements.
3. **Enumerate the witnesses.**  Preserve the actual command, arguments, environment boundary, exit code, test identities, skipped tests, and output artifact.  A shell wrapper that masks an underlying failure needs explicit treatment.
4. **Look for missing and adverse evidence.**  Which relevant checks were never run?  Did a new negative test fail on the original bug?  Did the verifier reject a malformed input?  Are there current red CI runs?  Do not let a passing subset erase an observed failure.
5. **Map each witness to one claim.**  A formatter pass supports a formatting claim.  A focused unit test supports that focused behavior under its fixture.  Neither alone licenses “the entire repository is correct.”
6. **Name the decision owner.**  Who can accept the remaining risk?  Is the action a local experiment, a merge, a release, or a customer-facing assertion?  Preserve “not decided” if the required authority has not acted.

The output can be a page, not a cathedral of schemas.  For each claim, show the best supporting witness and the best counter-witness or missing witness.  Give the reviewer the exact next command or source question that would change the decision.  The purpose is to shorten review without laundering uncertainty into approval.

## Why a hash is not enough

The fixture's captured files have SHA-256 digests.  The verifier checks copied packet bytes against the manifest and re-computes the script's internal packet hash.  That makes accidental or simple deliberate *post-capture mutation of the retained pair* detectable when the verifier is run against the retained manifest.  It does not make the original claim semantically correct.

It also does not establish a trust root.  The author could publish a new packet and a matching new manifest; the local hashes would agree.  There is no external signer or independently committed universe of attempted runs in this case-study pack.  The pinned Git commit identifies the source revision; after the article branch is published, its commit can identify the retained case-study files.  Neither establishes how the local subprocess was run.  Re-running the capture can check the source-bound behavior for another reader, but the reader should still inspect the source and the fixture before executing it.

This is why I would not describe this pack as “tamper-proof,” “audited,” or “reproducible scientific evidence” without qualification.  It is **an author-run local demonstration with retained raw outputs, integrity checks, and instructions for another reader to attempt a replay**.  That is valuable, and it has a smaller proof obligation than a safety or superiority claim.

## Re-run it, if you choose

After branch publication, readers can clone the public source and this case study and run the fixture without installing the companion MCP servers or using model credentials.  Inspect [`reproduce.py`](reproduce.py) before running it; it invokes the pinned repository script, which in turn invokes the literal shell commands `true` and `false`.  It sets `--no-memory` and does not request a ClaimLedger write.  It creates disposable directories under `/tmp`.  Do not run arbitrary future edits of any fixture program without reading them first.

The following commands assume this article branch, `docs/agent-claim-case-study-20260925`, has been published on the owned repository.  It is not merged into `main`.  For a fresh checkout after branch publication, use that branch and inspect the fixture before executing `capture`:

```bash
git clone --branch docs/agent-claim-case-study-20260925 https://github.com/RecursiveIntell/agent-memory-kits.git
cd agent-memory-kits
python3 docs/articles/agent-claim-boundaries/reproduce.py verify
python3 docs/articles/agent-claim-boundaries/reproduce.py capture --out-dir /tmp/my-agent-claim-replay
python3 docs/articles/agent-claim-boundaries/reproduce.py verify --out-dir /tmp/my-agent-claim-replay
python3 -m unittest discover -s tests -p 'test_evidence_workbench.py' -v
```

`verify` checks the retained pack without rerunning its source command.  `capture` is the operation that executes the fixed fixture commands, and it refuses to overwrite an existing output directory containing files.  Your new timestamps, temporary paths, trace ID, and byte hashes will differ.  The stable comparison is the source identity and the relationship between command, process outcome, and disposition, not equality of two randomly identified packet files.  The tested environment for this article was Linux with Python 3.14.6.  The repository's GitHub Actions workflow specifies Python 3.12, but I have not claimed that this article's capture was reproduced there.

For a more skeptical check, copy the retained `receipts` directory somewhere disposable, change the disposition in the copied broad-pass packet, and run `verify --out-dir` on that copy.  In my local check it failed with `broad-pass: packet bytes changed`.  Never edit the retained raw packet and then present it as the original observation.

The [capture manifest](receipts/capture.json) records the source hash and the exact packet hashes.  The three packet files remain inspectable even if you do not run code.  No PDF, video, hosted demo, reviewer endorsement, or proprietary service is required to see the narrow result.

## A review packet for a real change

The toy fixture isolates one failure mode, but a useful handoff has to survive more ordinary ambiguity.  Imagine an agent changes a parser, adds a test, runs that test, and says, “The parsing bug is fixed; all tests pass.”  A maintainer has at least two claims to evaluate.  The focused test might exercise the reported input; “all tests pass” additionally asserts something about the rest of the required suite.  The packet should not force the maintainer to infer the second claim from a screenshot of the first.

I would make the claims individually inspectable:

| Sentence under review | Minimum relevant witness | What remains open if only the focused test ran |
| --- | --- | --- |
| “The new fixture fails on the old parser” | Exact old source and failing test output, including the reason for failure | Whether the failure is the intended bug rather than a broken fixture |
| “The new parser handles that fixture” | Exact new source and passing focused test output | Nearby cases, error handling, and regressions elsewhere |
| “All required tests passed” | Declared required-suite inventory, actual suite invocation, test identities and final states | Missing, skipped, filtered, timed-out, or excluded cases |
| “The change is ready to merge” | Applicable policy, current-head checks, review decision, and any protected-branch gate | Whether the authorized reviewer has accepted remaining risk |

This table is a **proposed review method**, not a list of tests that this article ran.  A negative old-source test can strengthen a bug-fix claim, but even it does not prove universal correctness.  Conversely, a test failure can be genuinely unrelated to the patch; that requires a source-bound baseline comparison and an explicit exception, not simply dropping the result from the packet.  The unit of reasoning remains the claim, not the number of green checks.

### Time and source identity are part of the sentence

“Tests passed” is incomplete without *when* and *against what*.  A command result belongs to the source tree and environment that produced it.  If the agent edits a file afterward, a previous test can remain a true historical observation while ceasing to be evidence for the new tree.  The same is true when a dependency changes, a generated artifact is rebuilt, or CI runs at a different commit from the one about to be merged.  A receipt should bind these identities or say explicitly that it did not capture them.

That does not mean every note needs a cryptographic ceremony.  A local developer may only need a commit, a dirty-file list, a command, and an exit status.  A release involving a distributed build may require much more.  The rule is proportionality: make the witness strong enough for the decision being asked of it, and do not upgrade a weak witness merely because a downstream system has an approval button.  In this fixture the repository source is pinned, but the script's broad `promote` decision still depends only on the caller's supplied command outcomes.  Source binding answers one question; it cannot answer the missing coverage question for us.

### Privacy and selective disclosure

Evidence packs can also create a new problem.  Raw agent transcripts and tool output may contain credentials, private paths, customer data, or material that should not be posted publicly.  A credible review workflow needs to decide *what can be retained and shared* before indiscriminately logging everything.  A digest of private output can establish that a reviewer later inspected the same bytes, but a digest alone cannot show a stranger whether the output supports a particular claim.  When the underlying data must stay private, record who can inspect it, what public statement remains supportable without it, and what cannot be independently checked.

These candidate fixture packets use fixed commands and disposable paths rather than a model transcript or private dataset.  That limits what this example discloses; it is not a privacy assessment of other workflows.  The design makes this example easy to inspect, not representative of every real coding workflow.  If the decisive evidence in a future case is confidential, I would rather disclose a narrower claim than publish a persuasive-looking receipt whose support cannot be inspected.  Redaction and omission should have explicit boundaries, not disappear inside a confident verdict.

## Where this fits in the existing research

This is an engineering case study, not a priority claim over provenance research.  The LEDGER work explicitly builds layered claim-to-evidence trace graphs and treats those graphs as an aid to auditing agent workflows.[2]  ClaimReceipt asks whether a reported result can be recomputed from retained evidence *and* whether those records cover the committed experiment set.[3]  A survey of agent execution provenance also maps retrieved evidence, actions, memory, tool outputs, and final claims into a broader research landscape.[1]  My fixture is smaller: one published script, one concrete claim-support mismatch, and a capture you can inspect or rerun.

The same distinction is useful beyond coding agents.  A model can produce a plausible answer from retrieved documents without those documents genuinely supporting it.  A build can be provenance-attested without the shipped feature satisfying the product promise.  A benchmark can retain correct arithmetic over a selected subset while quietly omitting failed attempts.  These are related evidentiary questions, not demonstrations that this fixture detects all of them.  A future research paper would need a preregistered task universe, comparable baselines, a claim-support rubric, negative controls, independent assessment, and transparent error rates.  I have not performed that study here.

If I tried to turn this observation into a new general-purpose “agent truth engine,” I would inherit the hardest unsolved part: deciding which natural-language conclusions follow from which executions, across real projects and changing environments.  A useful first step is much less glamorous.  Admit only what the current command and source can actually witness, retain the uncertainty, and hand the consequential decision to the owner of that decision.

## The rule I am keeping

When an agent says “done,” I want a smaller sentence I can verify.  Which exact version did it act on?  What commands really ran?  Which required checks are missing?  Which claim does each result support?  Who is authorized to accept what remains unknown?

A receipt should make those questions easier to answer.  If it answers only the first one, I will not let its hash or its green label answer the rest.

## Sources

[1] https://arxiv.org/html/2606.04990v3 — From Agent Traces to Trust
[2] https://arxiv.org/html/2608.18398 — LEDGER: Claim-to-Evidence Trace Graphs
[3] https://arxiv.org/html/2609.01992v1 — ClaimReceipt
[4] https://docs.langchain.com/langsmith/observability-concepts — LangSmith Observability Concepts
[5] https://docs.langchain.com/langsmith/evaluation-concepts — LangSmith Evaluation Concepts
[6] https://raw.githubusercontent.com/RecursiveIntell/agent-memory-kits/77f8b6829e5fc09460c70553413cd0bd5560a8be/shared/scripts/evidence-workbench.py — Evidence workbench source at 77f8b68
[7] https://raw.githubusercontent.com/RecursiveIntell/agent-memory-kits/77f8b6829e5fc09460c70553413cd0bd5560a8be/tests/test_evidence_workbench.py — Evidence workbench tests at 77f8b68
[8] https://docs.github.com/en/actions/concepts/security/artifact-attestations — GitHub artifact attestations
[9] https://raw.githubusercontent.com/RecursiveIntell/Libraries/a53e4bf4398ce5873ffe65ac168409d0f4b32d16/agent-evidence-workbench/tests/release_truth_vertical_slice.rs — Rust AEW fail-closed regression tests
