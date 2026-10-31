# Cua QA hardening report

## Sprint state

This sprint is in progress. Two P1 findings are admitted and both are completed: issue #6 through PR #7, and issue #3 through PR #4 (merged 861cf16), each with merged-main verification. Two follow-up repairs are open: #12 / PR #13 (Hyprland 0.57) and the P2 #14 / PR #15 (Keyvault commit-point cleanup).

- Repository: `chrisohearn/cua`, verified remote `https://github.com/chrisohearn/cua`.
- Target: `main`.
- Starting target SHA: `7cc4bd0bfc3ce1a3246ae47fe02948dc9f64f010`. Current remote and fetched target SHA: `519d0e535fa75f508fd575939bb018f6d8286e5a`, tree `465dee9d9ad522e3aac9c6bc8368b965f7c243d6`. It contains the verified PR #7 repair and merged noncounting PR #9 prerequisites. Separate Ponytail PR #1/#5 work and its active successor PR #10 are excluded from excellence counts.
- Start: 2026-10-28 04:02 UTC.
- Coordinator: `mcp:2af09de7-b4a2-4a2d-81f4-e7552ba16143`.
- Tracker: https://github.com/chrisohearn/cua/issues/2.
- Accepted: 2 P1, issues #3 and #6. Merged and verified: 1; issue #6 closed. Completed P0: 0. P1: 1. F0: 0. F1: 0.
- Report PRs and tracking work do not count.

## Product contract

The root README promises computers for agents. Spaces manages desktop VMs and containers, live streams, teleport, sharing, and agent use. The Rust cua SDK and CLI own sandbox lifecycle and generated Python, TypeScript, Swift, and Kotlin interfaces. Cua Driver owns native desktop observation and input on macOS, Windows, X11, and compositor-specific Wayland routes. Lume owns Apple Silicon VMs. Bench owns task evaluation and trajectory export. CUA-S1 is a source-only research component.

Critical journeys include installation and first run, sandbox create/exec/remove, reconnect and cleanup, desktop observe/action/verify, host identity and authorization, file and process integrity, stream recovery, app persistence, and upgrade/rollback. Generated contracts, per-component releases, and explicit platform refusal behavior are required compatibility boundaries.

Trust boundaries include the host versus sandbox, client versus in-guest daemon, per-session target and capture scope, credentials and Keyvault approval, local versus hosted provider accounts, and installer/artifact provenance. Tests must use synthetic data and opt in to VMs, external services, and host input. `libs/fleet` is a read-only mirror. Deprecated packages are historical compatibility evidence, not a pretext to revive unsupported behavior.

## Instructions and ownership

Installed repo-excellence-sprint, chris-mode, revotech-engineering, revotech-tools, and revotech-github sources were read from `/home/cohearn/.codex/skills/`. Repository AGENTS, contribution, maintainer, security, RFC, CODEOWNERS, development, and test rules govern the work. Project memory is absent at the root. This report is coordinator-owned.

The Ponytail root owns independent simplicity work and releases admission at atomic handoffs. Its PR #1 merged67804e9 and PR #5 merged20a60e0e with exact reviewed/tested full-tree equality; their source reservations are released and neither counts here. Its original PR #8 is superseded by active PR #10 under the same correction lineage; that root retains the overlay, image-catalog/workflow, teleport/lockfile and benchmark-agent paths. This root retains PR #4's five paths. PR #9's nine-path aggregate prerequisite is merged; its shared Chromium changes reuse the peer's original commit through explicit handoff. PR #7's two source paths are also merged; detached actual-main worktree6 is retained for private proof and read-only discovery. This coordinator is the sole QA-report writer. Portfolio parents own maintenance/contribution gates.

The fork initially had `has_issues=false`. Enabling only Issues was completed and native readback confirmed `has_issues=true`. The portfolio coordinator explicitly authorized enabling only Issues as the reversible prerequisite for the mandatory lifecycle. Visibility, access, protections, Actions permissions, billing, releases, and other settings remain outside that setup action.

## Environment and baseline

Host: Linux x86_64, Omarchy kernel `7.2.8-10-omarchy`, Hyprland session. Available tools include Python 3.14.8, uv 0.13.5, Node 26.12.1, Docker client 29.9.2, and Rust toolchains 1.97.1 and 1.99.0. Component pin is Rust 1.97.1. Cargo is installed under `~/.cargo/bin` but absent from the initial PATH. The system Python lacks pytest; script tests use an isolated uv Python 3.12 environment. No shared desktop interaction is performed.

| Command or observation | Result | Limits |
| --- | --- | --- |
| `gh api repos/chrisohearn/cua/commits/main` | Verified starting SHA | No runtime claim |
| `gh api user`; repository permissions | `chrisohearn`, admin/push/triage | No production-system permission implied |
| Paginated fork open/all issue and PR REST lists | Empty before enablement | Issues disabled; upstream history requires candidate-specific deduplication |
| Main protection and rulesets | No branch protection; no rulesets | Required repository tests and review still apply |
| `node --test libs/cua-driver/tests/fixtures/shared/web/journal.test.cjs` | 2 passed | Shared fixture only |
| `bash scripts/ci/linux/preflight-rust-e2e.sh` | Lightweight readiness passed | Source driver and fixtures not built; no desktop certification |
| `cargo test --locked -p cua-driver-core --lib` with external `CARGO_TARGET_DIR` | 947 passed, 0 failed, 0 ignored | Pinned toolchain, no native behavior claim |
| `cargo fmt --all -- --check` in driver workspace | Passed | Formatting only |
| Isolated pytest of `.github/scripts/tests`, `scripts/install/tests`, driver script tests | 951 passed, 34 skipped, 6 failed, 142 subtests passed | Two Cargo-PATH failures and four inherited-XDG failures, reconciled below |
| `sh scripts/install/tests/run.sh` | 86 passed, 0 failed | Synthetic release on loopback, fake HOME and prefixes. macOS DMG checks skipped |
| Corrected PATH pytest of documented Cargo targets | 2 passed | Both original Cargo-PATH failures clear |
| Isolated-XDG pytest of `test_install_local.py` | 13 passed | All four inherited-XDG failures clear. This is seam/installer proof, not a native installation |
| `cargo test --locked -p cua-sandbox-core --test providers` | Build failed on disk quota | No test verdict |
| Scratch Fleet ownership reproduction, original disk run 95869 | Build succeeded; intended assertion failed: existing claim false, state false, one DELETE | Actual public sandbox API and loopback FakeFleet at starting SHA; no live provider |
| Issue #3 serial proof at `c26514862227e3a3308a25864610cf5c364ace88`, exec 12252 | Exit 0: focused regression passed, affected whole crates reported 253 passed, Clippy `--all-targets -D warnings` and workspace format passed | Live opt-in rows return without live execution. Public API/FakeFleet regression covers both pool paths; no live Fleet or native E2E |
| `bash libs/images/common/tests/test-browser-sandbox.sh` | 12 passed | Offline environment and launcher selection, no browser or image boot |
| Python candidate helpers | Initial selected-source proofs repeated under supported Python 3.12.14, then all three reproduced with normal package imports using existing source-built Fleet model bindings | Full unchanged modules, 67 imported modules and 80 source hashes checked. Native cua SDK endpoint/record and overlay substitutes remain; no VM boot, native Windows or E2E claim |
| `docker version` | Server access denied on `/var/run/docker.sock` | Container/VM paths unverified |

## Coverage map

| Area | Owner and current evidence | Remaining proof |
| --- | --- | --- |
| SDK, CLI, daemon, protocol and bindings | Read-only SDK discovery worker | Runtime, conformance, lifecycle, concurrency, generated drift |
| Spaces web UI, Electron and native host | Read-only Spaces discovery worker | Core workflows, persistence, recovery, parity, accessibility |
| Active Python and TypeScript, installers, images | Read-only package discovery worker | Safe local product and install flows, error paths, recovery |
| Cua Driver shared and platform behavior | Coordinator, contracts and baseline | Hermetic core/protocol plus canonical exact-SHA desktop matrix |
| CI, releases and artifact contracts | Coordinator, script baseline | Component distribution and upgrade verification |
| Lume and macOS native behavior | Documentation mapped | Apple Silicon and logged-in disposable macOS environment |
| Windows native behavior | Canonical runner mapped | Interactive Windows environment or hosted canonical lane |
| Linux X11 and Wayland | Lightweight local readiness only | Disposable canonical and compositor-specific lanes |
| Concurrency, bounded stress, interruption and recovery | Not yet exercised | Reproducible workload per critical workflow |
| Security and isolation | Read-only auth and Keyvault trust-boundary mapping on actual main519d | Private deduplication and safe hermetic proof; private disclosure if validated |
| Final fresh adversarial search | Not started | Fresh assessment after coverage pass |

## Candidates and accepted findings

Issue #3 is admitted as P1 after real sandbox-core/FakeFleet execution proved the existing claim and state were deleted. The root-cause and objective criteria are in https://github.com/chrisohearn/cua/issues/3. Issue #6 is separately admitted as P1 after normal-import registry-only QEMU proof and historical deduplication. Remaining leads require proof and final deduplication. A test failure alone establishes neither a root cause nor severity.

| Lead | Evidence and proposed proof | Disposition |
| --- | --- | --- |
| Existing named Fleet claim deleted by failed create | `cua-sandbox-core::create` preserves only Local pre-existing resources. A scratch public-API/FakeFleet reproduction asserts claim and state survival after a readiness failure | Reproduced after disk recovery: existing claim false, state false, one DELETE. Issue #3 admitted. Similar Spaces cleanup remains a lead |
| Native append retry duplicates a partially appended prefix | Client fallback starts another append after retryable native failure; real server writes directly | In-process real-server fault proof pending |
| Rejected stdin write poisons sequence counter | Client increments before server validation; oversized rejected write does not advance server sequence | Real in-process server proof pending |
| Cloud `wait=false` loses cancellation journal before provisioning finishes | Background claim finalization outlives tracked create completion | Existing cancellation test variation pending |
| Python destroy after reconnect or resume does not own runtime cleanup | Reconnect and resume construct handles without runtime fields | Source-seam reproduction returned; normal-package Python 3.12 proof reproduced through unchanged modules and SDK-boundary recorders; root admission pending |
| Registry-backed QEMU image layers become rejected `disk:` reference | Normal-package Python 3.12 reproduction without a disk override runs actual selection/backing/cache code and observes exact refusal before resolution/create | P1 issue #6 completed through PR #7 at reviewedf3c, merge1769/tree3672. Baseline9 intended failures/candidate9 passes; merged-main two owners43pass/2fixture skips, private wheel+sdist canonical metadata/content smoke pass. All applicable final-head CI and Code/Security pass; original3P2 limitations remain unfixed/nonblocking |
| Direct Windows PTY defaults to Unix shell | Direct connect has no environment metadata; PTY selector chooses `/bin/sh` | Source-seam reproduction returned; normal-package Python 3.12 proof reproduced through unchanged modules and SDK-boundary recorders; root admission pending, no native Windows proof |
| TypeScript agent HTTP body wait exceeds timeout | Unchanged public client, real Node fetch, loopback body stall: 100 ms timeout still pending at 650.81 ms; healthy JSON completes in 12.83 ms | Rejected for this sprint cutoff: the source package is listed in the workspace but the public npm registry returns 404 and no release workflow was found, so current evidence does not establish a realistic major supported-user impact. No issue or repair |

The ownership lead was compared with upstream PRs #4468 and #4560. #4560 landed local borrowed-sandbox protection and explicitly excluded other cleanup paths. #4468 remains open upstream and is not this sprint's claim. Neither has a closing issue. Any admitted cloud repair must preserve that lineage, avoid those deferred changes, and explain distinct scope.

Fork all-state issue and PR queries were empty before Issues enablement. Focused upstream issue and PR searches found no matching cloud readiness, append, stdin, Python destroy, layered-QEMU, or Windows-terminal issue. Search results alone do not prove exhaustion. The local lead checker recorded the Fleet and three Python candidates as NEW.

## Reviews, repairs and merges

PR #7 is merged and issue #6 is closed after main proof; accepted2, merged/verified1. Issue #3 / PR #4 remains open. Every repair retains its original identity and correction history.

### Issue #3 / PR #4

Ready PR https://github.com/chrisohearn/cua/pull/4 is published at `60dc95c4cf4b8b5a4b20fce765f542e52b6f3082`, tree `cb3d10c5da1a7b5ccc8c1ec9f27db55200626ad3`. Branch `fix/3-preserve-fleet-sandbox`, isolated `runtime/cua/worktree-3`. It merges verified main519d after PR #9 and retains exactly five changed paths. Four product/test/generated-document files are byte-identical to the previously proven101/16e source; only the owned CI workflow additionally gives macOS 90 minutes instead of60. All checks, commands, runners and other workflow fields are preserved. Fleet acquisition provenance, borrowed claims/state and stored credentials remain protected; new-claim cleanup and Local protection remain covered.

Original command12252 ended0 on runtime head `c26514862227e3a3308a25864610cf5c364ace88`: focused regression, affected whole crates (253 reported pass), scoped Clippy and format passed. Opt-in live rows return early; they are not E2E. Hosted Code/Security completed clean on c265. CI then found introduced generated Fleet-reference drift. Same issue correction1 canonically regenerated the missing declaration. Original24039 ended0, generated/check passed, and only the reserved MDX changed. Runtime/CI/test hashes stayed identical, preserving their proof.

Exact101 Security completed clean; its historical Code review remained running without a finding. Original observers48041/50123 ended5 at local watchdogs with failover=false. PR4's four pre-existing external-link failures were resolved through merged PR #9. Exact16e Code completed at15:58:48Z with one introduced P2; Security completed at15:59:32Z clean. All applicable current-head CI remains required.

The P2 stateless managed-pool reattachment limitation can discard an explicit CUA_ENV_TOKEN/CUA_SPACESD_TOKEN when no saved token exists. Its provider P2 badge is retained; no P1 impact is established. Root initially proposed correction3, then withdrew that P2 proposal before any edit, push or new review after reconciling the installed cutoff. The limitation is explicitly unfixed/nonblocking in review reply4402977241; it consumes no correction round or finding count and remains unchanged on60dc. The later necessary CI-budget correction is separate from that withdrawn P2 proposal and retains issue3's existing lineage.

Current-head macOS CI exposed two causes. Swift blocks failed twice before runner acquisition, while uninstall and example Swift also initially failed before acquisition; runner_id0, empty steps and capacity annotations are retained. No third unchanged Swift retry was requested. Rustmacos actually ran: native Clippy15m18pass, initial Spaces ownerpass, broadtest compilation36m02, long test completed successfully and Fleet preservation regressionpassed, then the job reached its60-minute deadline. Full later owners remained unexecuted, so this was not a pass. Same-PR necessary correction60dc changes only the macos-26 budget60->90; static YAML preservation/diff checks pass. Fresh Code/Security and every required current-head CI remain binding. No local heavy/native proof or new sprint finding/count is created.

Local worktree3 formerly contained unpushed `b0fc15e4a546f567be8ed95ff8ad20d7a44fc374`, tree `63332c62b83f9ba69ee808a50a5f9f1add30e829`, containing only the four source permalinks beyond101. Its original patch shipped through PR #9. Merging verified main519d into the existing PR #4 branch removed those duplicate paths from the relative diff without rewriting history; no reset, successor or count was created.

### Issue #6 / PR #7

PR https://github.com/chrisohearn/cua/pull/7 merged normally from exact reviewed head `f3c5d3da24b91bc5c03b558c37733437e00fb296` to main `1769c2ece0dadd0618c9f86920d43a62f765ed26`. Native PR/main/commit readback and fetch verify merge parents20a60e0e,f3c5 and tree `3672ec69d59d72039d0eec829c1a81cf92c993f9`, exactly equal to the tested/reviewed head. Only qemu.py and its existing runtime-adapter test owner differ from base20a. The original source4f0/treec0f remains retained; guarded integration of verified PR5 main20a changed neither original source hash.

Original native-binding proof21752 ended0: pinned Rust1.97.1 locked offline SDK build, actual generated Python bindings and source-built lib SHA256 `b4925ce340bf7fb3d9f529758847c4b8f0b0e7e85c56b225e5d4785d6986d6b6`. Baseline9 intended failures/0errors/0skips; candidate9passes; two complete owners43pass/2cloud-fixture skips/1existing warning. Hosted Python proof851pass/112explicit skips additionally covered those two local fixture cases; live/backend skips remain unverified. Scoped Ruff/format and disk-override controls pass.

All11 applicable pull-request workflows passed atf3c; three target-event gates were separately verified. Exactf3c Code completed08:45:46 and Security08:47:08 clean. Root reread every review submission, inline thread and conversation before merge and again afterward. Original3P2 notes remain explicitly unfixed/nonblocking: secret-only capability probe, Windows image-env startup refusal and synchronous cold lookup. The earlier proposed P2 correction was withdrawn before edits and consumed no repair round. No common runtime source or native control changed.

Guarded ship readiness original82048 and merge67420 actually ended0. Post-merge original99156 actually ended0 at10:34:08.548490Z: actualmain1769 ran both complete owners43pass/2samefixture skips, including all9 regression cases. A private wheel283574B SHA256c8e1c2205e4954fb298208cffbd258f10ad9140e8e869f5aa91021d2825b0a7b and sdist241013B SHA2568b64f44381396fa0669d86ce5290b8a557c47a84649be78d1fe53d47b70c2766 built with the declared Hatchling backend. The canonical resolve_sandbox_release.py metadata/source-version checks passed; both archives contain exact merged qemu.py bytes. Nothing was installed/published. Evidence: runtime/cua/postmerge-6/{receipt.json,owners.log,owners.xml,build.log}.

Issue #6 closed completed at10:40:15Z after that proof. One distinct P1 counts. Native VM boot, real provider/registry, Windows and desktop E2E remain gaps; synthetic endpoint/post-boot recorders are not native execution. PR7 monitoring stopped; branch and detached worktree remain preserved for current source-only coverage.

### Shared prerequisite / PR #9 (noncounting)

https://github.com/chrisohearn/cua/pull/9 merged reviewed head `d0431be7d6c8ffee713ad8ceff0fc17c225aba25`, tree `183f91dd241b157bfdbb624283a241b655f00d05`, as main `519d0e535fa75f508fd575939bb018f6d8286e5a`, tree `465dee9d9ad522e3aac9c6bc8368b965f7c243d6`. It retains original four immutable source links, peer Chromium two-pin commitb298 with provenance, upstream AppKit5665 bootstrap backport and strict window-origin polling repair. Exactd043 Code/Security were clean and all14 applicable pull-request workflows plus four target-event runs passed. Post-merge proof confirmed all nine reviewed paths byte-identical, prior PR #7 QEMU paths unchanged, workflow owner15pass, geometry8pass, and QEMU integration owners43pass/2expected skips. No native/container execution, install, publish or deploy occurred. Upstream contributor Dillon DuPont was notified on PR5665. This is a noncounting prerequisite.

On old471, all four repaired source URLs resolved in lychee; the only external-link failure was unchanged `https://agentclientprotocol.com/` returning500. No policy suppression or unrelated source edit was made. Image Doctor failed because the fork ledger lacked the newly moved Omarchy child digest `sha256:fc4d5a56ad79755120db992a7b2da562745930b5f6eb5f80f4d07494e23790b0`.

Root qualified authentic upstream ledger04b4d55db669bd856942869eba3841932d852034 as one commit ahead/zero behind forkab24d2a2. Its exact digest record contains passing strict QEMU and QEMU-claim-secrets lanes (113pass/11skip/0fail each) from successful canonical run40638173204. Under ordinary admission, the fork ledger was fast-forwarded with force=false and expected oldsha, then native readback verified exact04b4d55. No report, baseline, workflow, protection or policy was edited. Historical upstream Doctor records do not establish local native test capability. New-head checks must fetch and validate that authentic evidence.

## Environment limits and correction history

No local heavy command, queued build or host-resource reservation is held. The PR9 merge completed at15:29:39Z within its lease. That lease expired at15:52:26Z; the read-only scratch main smoke began at15:53:02Z and passed, so the 36-second verification timing gap is retained honestly. A fresh admission was acquired afterward for report closeout and PR4 integration. The earlier PR7 release readback separately returned `LOST` after its lease expired. Read-only source workers need no mutation lease. Every actual END callback for21752 was delivered to parent/14f/395. QA remains sole-coordinator owned and user edits are preserved.

Earlier quota failures, terminated migration9327, actual successful disk continuation95869, canonical-docs long-socket failure and corrected short private TMP continuation remain preserved in logs/workpad. Migration9327 never completed; only confirmed inactive owned disposable outputs were removed. Initial nightly setup used the user Rustup prefix before the private-prefix correction; root default1.99 and SDK pin1.97.1 remain unchanged. No shared toolchain/cache was deleted and no pressure error is counted as a product finding.

Docker socket access remains denied. Portfolio and historical owner confirmed no qualified reusable nonproduction Lume/macOS environment; the user's signed-in real Mac is excluded. Native Windows and canonical Linux desktop certification are also unverified. No source-only proof or successful SDK compilation closes those gaps. Append, stdin, cancellation, stress/recovery and fresh final adversarial coverage remain incomplete.

## Separately owned work

Ponytail PR5 actually merged20a60e0e with reviewed2f73 tree equality and post-merge mocked-login proof. Original PR8 is superseded by PR10, which remains wholly with that root under its existing high-water correction lineage and owns its current source/review/CI/merge gates. Original clean6135 proof (199Rust, fake-handler checks,321benchmark pass/2existing skips) remains peer evidence, not an excellence completion. Coordinator PR5 assistance was title metadata only; no count/ownership transfer. PR1 merge67804e9 and other unrelated simplifications remain excluded.

## Final disposition

IN PROGRESS / NOT_LANDED. Accepted2, merged/verified1 (P1 issue6). Tracker2 stays open. No final report PR or comprehensive-exhaustion claim exists. PR9 is merged and verified; PR4 is refreshed on current main and remains the only accepted repair not landed. Fresh exact-head review, CI, protected landing and post-merge proof remain binding.

## Joined lifecycle checkpoint — 2026-10-29

Chris's joined Repo Excellence and Ponytail request retains this root as the single Cua coordinator. Remote main remains519d. GitHub has two open issues (#2 tracker and accepted P1 #3) and two open pull requests: owned PR #4 and separately owned Ponytail successor PR #10. Issue #6 / PR #7 remains the sole completed qualifying lifecycle. PR #4 exact head60dc is mergeable; exact-head Code and Security reviews were requested once on this checkpoint, while required hosted CI, merge and fetched-main proof remain binding.

The private Keyvault file-anchor probe remains unadmitted and undisclosed. Attempt1 stopped before compilation on an offline `argon2` cache miss. A separately authorized frozen-lock Linux fetch downloaded only `argon2 0.5.3`, `blake2 0.10.6` and `password-hash 0.5.0`; all archive checksums match the frozen lock. Attempt2 is prepared but unexecuted: `run-attempt2.py` SHA256 `4b681cd34034c3170128170bc95f62d8aaaa2d28d7a1cde77143c6634a76320d`, bindings SHA256 `c88760ffa600079a5506dbcbf82995fc65032b7e333260751dea5734b2117f68`. It uses a new private target/log/result namespace, performs no fetch or lock regeneration, and awaits separate finite qualification. No Keyvault finding, severity, issue or count is admitted.

## Historical continuation log (superseded where the checkpoint above differs)

PR5 actual merged main is20a60e0e6043e3b4187a74c13d3723d7d04069e7/treee29bc559d4e46b32a8d0eb6afa341e79276b6a08. PR7 now guardedly integrates it atf3c5d3da24b91bc5c03b558c37733437e00fb296/tree3672ec69d59d72039d0eec829c1a81cf92c993f9; original two source/test hashes are identical and relative-main diff stays two files. Focused complete owners reran43pass/2local fixture skips; old native851pass CI covers those two cases. Exactf3c Code/Security and CI are pending. The original3P2 notes stay unfixed/nonblocking; no P2 repair or new count.

The one qualified real-server stdin attempt actually started08:37:13.089969Z/PID851146 and ended1 at08:37:13.141222Z. Offline lock generation PID851147 ended101 because private index lacks mime_guess. No lock, build, runtime or server/child ran; both PIDs absent, source/admission/resources released. All31 source hashes matched baseline7cc; no downloads/install/substitution or unchanged retry occurred. This remains an environment gap, not a product finding.

PR9 exact8b32 image build installed Chromium156 and reached its suite. Run40651371434/job122692463253 failed one Python docs sidecar case: busybox:1.36 pull returned Docker500 unauthorized. The initially printed top-level-await SyntaxError is handled by the bootstrap and is not the terminal failure. Root corrected that initial diagnosis; no docs/harness edit is justified by it. A bounded file-read-only child traces parity/pull behavior. No registry retry or local Docker/native build has run.

PR9 exact8b32 source Code/Security completed clean with zero findings. Docs links and Doctor required checks pass. Required remaining attempts: container job122692463253 failed busybox pull500 unauthorized (Chromium/image setup succeeded), and AppKit job122691976316 failed observation missingcapture_id after disposable hosted permissions true; eight other jev-use jobs pass. One unchanged-head retry of each was requested via native API. Outcomes remain pending; no source/auth/control workaround or local macOS capability is inferred. The source-only triage rejects a proven-transient claim from the first failure alone.

## AppKit prerequisite continuation

Exact8b32 AppKit retry2 job122718450254 failed at the identical missingcapture_id guard; eight siblingjobs pass. No third unchanged retry. Upstream dedupe found already-merged trycua/cua PR5665/original43fba306abc8857c9585a8977c01cb94bb268d61 fixes this same releasedDriver>=0.37 CI setup: record the existing signed app direct-capture approval before daemon startup and read it back, using the identical pattern already present in this repository's canonical hosted Rust E2E bootstrap. It changes no product/native Driver code or broader permissions/identity/target. This is a noncounting CI backport, not a newly completed issue or local Lume route.

Local worktree-doc-links candidate c9bf61567074704deb6ed566f27aed0b97e20bb8/tree034f3381ee3efeff8d532e8754dd9a42486a6ea4 normally integrates main20a60e0e, then reuses original43fba306 with -x, original Dillon DuPont author/GitHub-linked email, original Claude coauthor and adapting Chris coauthor. A single launch-line conflict was resolved by preserving the fork launch command and adding only the original13 approval lines; all18 source/test additions match upstream, all five previous candidate hashes match8b32. The added keeper failed on the exact missing approval assertion before the fix; all15 existing workflow-owner tests pass afterward. All other jobs, workflow triggers/permissions and only existing AppKit grant step preservation were parsed/asserted; bash syntax passes. No local native action, shared cache/config write, install or heavy build ran. Cached PyYAML6.0.3 was read with bytecode disabled.

This candidate is LOCAL ONLY at this observation: remote PR9 remains8b32 while its prior controlled container retry2 is running. Do not claim c9 pushed, reviewed or merged. Fresh exact-head Code/Security and every applicable CI remain required after publication. Source admission is released across that CI boundary. Third-candidate convergence is justified by the retained required-CI repeated failure and exact already-merged upstream fix, without new issue/count/reset.

A private AppKit attempt2 log was initially written to a relative ignored artifact path by root, so the read-only child could not consume its assigned log. Root actually read both native API logs; that child return remains source-only. Root moved only its confirmed own artifact to the correct private path, preserving SHA25615cf8e6a50b89a32a40207875f30ea483934d390cbaf15aad09f99f03cc6c3b9. No user source was reverted or removed.

## Published aggregate prerequisite

PR9 is now actually pushed/ready atd0431be7d6c8ffee713ad8ceff0fc17c225aba25/tree183f91dd241b157bfdbb624283a241b655f00d05, titlefix(ci): restore image and documentation test prerequisites, nine paths. Earlier localc9 is preserved in its ancestry with original5665 author/coauthors/-x; no head/history reset. Original8b32 controlled containerretry2 actually ended1: every docs block passed, but run-omarchy geometry returned empty stdout and was accepted as a truthy process object. Normal actual-helper/SDK import reproduced exactValueError afteronecall despite a subsequent valid result. A minimal predicate now requires successful exit plus two integers within unchanged poll bounds/shell. Existing test_desktop owner adds8recording-boundary cases:6fail/2pass before,8pass after; zero/negative origins and exact30-attempt failure are covered. Six real desktop cases were deselected locally, not claimed native passes. ScopedRuff/diff and shell-output stub proof pass; originalAppKit15owner result is reused against identical source hashes. One first keeper collection failure from pytest.ini selecting the unstaged SDK path was retained and corrected to the actual private staged SDK, no mock/published substitute.

All prior seven file hashes except the two new geometry paths remain bound. Fresh exactd043 Code/Security requests were posted once; all required finalhead CI, normal merge and main proof remain pending. This aggregates the current compatible requiredCI blockers before publication; no new major finding/count or correction reset is created. Source admission is released across the ensuing gates, and no local heavy/native process is held.


## Current verified merge wave

As of2026-10-28T10:40Z, issue6 is completed and closed; main1769/tree3672 is verified. All older pending PR7 statements below earlier continuation headings are historical and superseded by the issue6 section above. PR9d043 source reviews are clean; current workflow set has14 distinct pull_request workflows (one metadata edited-event duplicate), with no observed failure at the first complete readback and six lanes still pending. Original8b retry2 results are preserved: all29docs blocks passed, one geometry failure; repeated AppKit missingcapture_id. No third unchanged retry occurred. Current correction proof is not a native/Lume claim.

Two source-only auth and Keyvault discovery packages completed at frozen actualmain1769/tree3672 under declaration142bae4cfcea152cee52736aa78475a3c49dab00af9d5bcf82d159ec75813847. Both had empty write ownership and performed no Git, execution, network, account or native action. Authentication mapping retained two credential-lifecycle leads; Keyvault mapping retained five potentially security-sensitive authorization, delivery-ledger and storage-consistency leads. They remain private, deduplication and deterministic hermetic proof are pending, and no runtime result, severity, issue or count is admitted. All delegated children are complete.

Tracker #2 was refreshed after independent issue #6 readback: accepted2, merged/verified1. Issue #6 is independently confirmed `closed` with reason `completed` at2026-10-28T10:40:15Z. PR7 monitoring is off. PR9d043 Code and Security are clean. Thirteen of fourteen distinct current-head workflows passed; the Swift docs job was never acquired by a hosted macOS runner and was canceled with a capacity annotation before any step or log, while its Kotlin sibling passed. One bounded job-only retry is queued as job122908713122; no source/environment defect or pass is inferred. PR4 issue3 remains the only accepted repair not yet landed, and its exact101 Code review still reports running without findings or provider failure.

PR4 exact60dc readback at2026-10-29T15:5xZ: Code review reports no major issues; the only open thread is the retained nonblocking P2 env-token limitation. Security review shows completed, but its finding details are still loading and no finding comment exists; no claim is made from it. The thirteen non-macOS current-head workflows pass. All six non-passing macOS jobs (rust, bindings drift, swift smoke, uninstall, swift blocks, infinite-canvas) were canceled with `not acquired by Runner of type hosted` capacity annotations, zero steps and no runner, so they show no source defect and no pass. The repository is public, so hosted macOS reruns create no spend. One failed-job rerun was requested at15:55:02Z for runs40732168265, 40732168717 and40732168346. Infinite-canvas run40732168605 already used its one retry (attempt2, also not acquired) and is not retried again. The Keyvault attempt2 finite slot (06:04Z) was returned unstarted after a provider turn failure: no process, output, log or target exists, and its wrapper and bindings hashes are unchanged. It needs a fresh finite qualification and will not be retried from a general push.

PR4 exact60dc rerun outcome, read back at2026-10-29T18:45Z. Swift smoke (macOS) rerun job123562074661 acquired a hosted runner and passed every step, including the dev dylib, the spaces-sdk-swift overlay and the XCFramework target (16:00:06Z to16:56:38Z). Four reruns were canceled again before acquiring a runner, with zero steps and capacity annotations: rust (macos-26) job123562075505, bindings drift (macos-26) job123562075295, macOS uninstall regressions job123562085490 and swift blocks job123562096121. Infinite-canvas swift test is still not acquired after its earlier retry. Five macOS checks therefore have no executed result on60dc. They ran no code: they are neither a failure nor a pass, and hosted capacity is not treated as a CI exception. Each check's retry budget at60dc is consumed. PR4 stays open and NOT_LANDED; the issue3 count is unchanged. Runner labels: swift blocks uses macos-14; the other four use macos-26. Parent disposition: no further retry is allocated now. The five-check retry request stays PARKED until a relevant, real capacity change and a separately qualified bounded disposition, or an authenticated owner decision within existing proof and retry limits. No source change, no test weakening and no local macOS substitute.

Triage of new automated issues, 2026-10-31T06:1xZ (main still519d; PR4 unchanged and parked). Issue #12, Hyprland plugin requalification: the arch and omarchy-edge rows (Hyprland 0.57.0-1) fail at CMake configure with `Input is pinned to Hyprland 0.56.2` (`libs/cua-driver/hyprland-plugin/CMakeLists.txt:249`). This is the deliberate version gate, not a product defect: the plugin refuses an unqualified ABI instead of loading misbehaving input hooks. Both 0.56.2-4 channels (omarchy-rc and omarchy-stable) pass build, CTest 20/20, load and input smoke. Supporting 0.57 is a requalification port under `requalify/COMPAT-BRANCH.md`. It needs native Hyprland 0.57 validation, which this root cannot obtain without the user's live compositor (excluded by the Hyprland lease constraint and the host-input rules), so no excellence finding or count is admitted. The host itself now runs Hyprland 0.57.0-2 without the cua plugin, which shows the port has real user impact; it is routed to the requalification owner. Issue #11, the scheduled Omarchy image rebuild, failed when the third-party mirror.omarchy.org returned a package signature over pacman's 16 KiB limit (`cloud-guest-utils-0.33-3 ... .sig`). This is external mirror behavior with no repository-source defect shown. The image release path is outside this root's authority, so no repair or count is made.

Owner instruction "Fix all" (Chris, 2026-10-31) unparked the gated items. Outcomes:
- PR4: one owner-directed rerun of the five capacity-cancelled macOS jobs acquired runners. All 40 checks passed at exact head 60dc95c. Merged 17:56:38Z as 861cf16 (parents 519d and 60dc). Its tree cb3d10c equals the tested head tree. Post-merge: the cua-sandbox-core providers `fleet_` tests passed 14/14 on 861cf16, including the reattached-claim preservation regression. Issue #3 closed as completed. Counts: accepted 2, merged/verified 2.
- #12: draft PR #13 (1e5719f2b), since marked ready. Exact-version input allowlist for 0.56.2 and 0.57.0, plus four API helpers. Local build against 0.57.0 headers with -Werror passed, and CTest passed 20/20. An independent review found nothing blocking. Noted: 0.57 refuses input to windows that do not accept input, which fails safe. The CI requalify matrix, including the 0.56.2 path, is pending.
- Keyvault attempt2 ran once (17:56:13 to 17:56:57Z; build 43s, probe 1s) and returned SOURCE_PREDICTED_OBSERVATIONS_MATCH. The fault case showed that `upsert_items` deleted new payloads after the sealed index had committed, when the anchor write failed. Rated P2 (error-path integrity, heals on rewrite, not exploitable), so it is not counted. Tracked as public #14 with no exploit detail; fixed in PR #15 (8a451414a) with a mutation-checked regression test. cua-keyvault: 160 tests, clippy and fmt pass.
- #11: no repository defect. The external mirror served a bad signature. Not retried.
- New blocker: GitHub starts no new Actions runs for this account. workflow_dispatch returns 422 "Actions has been disabled for this repository", and PRs #13 and #15 report no checks; only reruns of existing runs execute. That needs the account owner, so #13 and #15 cannot meet the CI gate until Actions is restored.

Actions restored, 2026-10-31. Correction: the CI stall was not account-wide. GitHub had disabled workflows on this fork for wasted compute ("Workflows on this fork have been disabled"); other chrisohearn repositories kept running. With the owner's choice ("Enable, schedules off"), the 18 registered scheduled workflows were disabled through the API, Actions was re-enabled on the fork's Actions page, and PRs #13 and #15 were closed and reopened to trigger PR CI. The Hyprland requalify workflow was enabled only to dispatch run 41233784915 on `fix/12-hyprland-0.57` (publish_manifest=false), then disabled again. Three scheduled workflow files on main are not yet registered by GitHub: cd-image-macos.yml, ci-cua-driver-installer-compat.yml and ci-test-models.yml. They cannot run until a push to main registers them, and they must be disabled after the next merge to main.

Fork refactor, 2026-10-31 (owner decisions). Chris has pull-only access to trycua/cua, so the fork stays as a contribution fork.
- Fork main was reset to mirror trycua/cua main at d1fe368a6, using force-with-lease from d813aa2. The old main is kept as `archive/fork-main-20261031` (d813aa2), which holds every count, merge and report above. All 51 upstream scheduled workflows are disabled on the fork. The 46 push-triggered runs started by the reset were cancelled.
- Upstream PRs from fork branches, each re-tested on d1fe368a6:
  - trycua/cua#6253, Hyprland input detection. Supersedes #6153 and refs #6232 and #5751. Build with -Werror passed against 0.57.0; CTest 20/20.
  - trycua/cua#6254, Keyvault batch-commit consistency. 167 tests; clippy and fmt clean.
  - trycua/cua#6255, QEMU registry layers. 27 adapter tests pass, and 9 fail when the fix is reverted.
  - The fork Fleet fix (PR4) is obsolete upstream, where the Fleet adapters were removed.
  - Fork PRs #15 and #16 are closed as superseded.
- Peer claim recorded: the Ponytail root is preparing its original benchmark-wrapper and teleport-crypto cleanup as a separate upstream contribution. It covers four agent files, `cua-teleport/Cargo.toml` and matching lock edges, with no overlap with these PRs. Its fork PR #10 is not merged here.
- Host cleanup:
  - Removed the Omarchy `cua-driver-bin` 0.33.4 package. It shadowed the running 0.35.4 build on PATH and nothing referenced it.
  - Deleted six fork branches whose work is merged or superseded.
  - Removed finished worktrees and about 11 GB of build caches.
- The Cua Driver rebuild from upstream main plus PRs #4934 and #4931 is in progress. A trial merge conflicts in 16 hunks across the browser consent and existing-profile code.

Host Cua Driver updated, 2026-10-31. The running build (0.35.4-hyprland-811d8cd4, unmerged branch) was replaced by 0.38.0 built from d834330d0. That is a merge of trycua/cua main d1fe368a6 with Chris's PR #4934, which includes #4931.
- Release build with `--features cua-driver/portal-input`. Tests: cua-driver-core 1157 passed, platform-linux 753 passed (one Xvfb-only test not run), cua-driver 460 passed. Clippy reports 15 findings; every one is blamed to an upstream commit.
- Installed side by side under `~/.cua-driver/packages/releases/0.38.0-main-d834330-*`, and `current` was switched atomically. Rollback: point `current` back at `0.35.4-hyprland-811d8cd4`, which is kept.
- cua-driver.service and agent-desktop-cua were restarted. Checks after the restart: the host socket answers; `agent-desktop doctor` is all ok; on the agent display, existing-profile prepare, exact bind and a semantic_v2 snapshot all work. No Hyprland config edit or reload happened.
- The merge was fast-forwarded onto PR #4934's branch, which is now mergeable, and a summary was posted there.
- Removed the shadowing Omarchy `cua-driver-bin` 0.33.4 package and pruned 13 old driver releases (898M → 123M).
- Upstream review follow-ups:
  - #6253: release allowlist (737b0e618).
  - #6255: readiness after post-boot layers (68770d26b).
  - #6254: link-staged restore, repair of missing records, and staged-link cleanup (1c610a3d5, f22e499a9).
  - All are mutation-checked. CI on all three awaits maintainer approval of fork workflows.
