# chrisohearn/cua: agent guide to this fork

Read this before you work in this repository. It covers only what differs from
upstream [`trycua/cua`](https://github.com/trycua/cua). For everything else, the
upstream docs listed in [Upstream docs that stay authoritative](#upstream-docs-that-stay-authoritative)
apply unchanged.

## Why this fork exists

- **Contribution fork.** Chris (`chrisohearn`) has pull-only access to `trycua/cua`.
  Every upstream pull request opens from a branch here.
- **Source of the host Cua Driver.** This Omarchy machine (Linux, Hyprland) runs a
  Cua Driver built from a fork branch. That build carries open upstream PRs
  that have not shipped in a `cua-driver-rs-v*` release yet.
- **Not a long-lived variant.** On 2026-10-31 `main` was reset to mirror
  `trycua/cua` `main`. The old fork history is kept on `archive/fork-main-20261031`.
  `main` now equals upstream plus this guide and the `AGENTS.md` pointer block.

Retire the custom host build when the PRs in [Divergence](#divergence-from-upstream) that it
carries ship in an upstream `cua-driver-rs-v*` release. The fork itself stays
for as long as upstream PRs need a head repository.

## Where our build is used

All paths are on the Omarchy workstation, user `cohearn`, `HOME=/home/cohearn`.

| What | Where | Notes |
| --- | --- | --- |
| Installed driver | `~/.cua-driver/packages/current` → `releases/0.38.0-main-6e5a0cd-x86_64-unknown-linux-gnu` | Built from fork commit `6e5a0cd9d` (branch `host/hyprland-seat-lifetime-0.56.2`); `BUILD-PROVENANCE.json` in the slot. Previous build kept for rollback: `releases/0.38.0-main-86e6db7-x86_64-unknown-linux-gnu`. |
| `cua-driver` on `PATH` | `~/.local/bin/cua-driver` → `~/.cua-driver/packages/current/cua-driver` | Every consumer below resolves the binary through this symlink. |
| Host daemon | `cua-driver.service` (`~/.config/systemd/user/cua-driver.service`) | `cua-driver serve --permission-mode unrestricted --dangerously-bypass-approvals`, `CUA_DRIVER_RS_ENABLE_WAYLAND=1`. Socket `~/.cache/cua-driver/cua-driver.sock`. Drives Chris's own screen; use it only when he asks. |
| Agent desktop daemon | `agent-desktop-cua.service`, part of `agent-desktop.target` | `agent-desktop run cua` starts `cua-driver serve --socket $XDG_RUNTIME_DIR/agent-desktop/cua.sock … --no-overlay` on invisible display `:42`. Agents do all browser work here. |
| Agent desktop product | Repo `Revotech-Networks/agent-desktop`, checkout `~/Developer/Revotech/Projects/agent-desktop`, installed at `~/.local/share/agent-desktop/app/agent-desktop` (`~/.local/bin/agent-desktop`) | Overrides the driver path with `AGENT_DESKTOP_CUA`; defaults to `~/.local/bin/cua-driver`. |
| MCP clients | Claude Code user MCP server `agent-desktop`; Codex `[mcp_servers.agent_desktop]` in `~/.codex/config.toml` | Both run `cua-driver mcp --socket $XDG_RUNTIME_DIR/agent-desktop/cua.sock`. |
| Auto-update | `cua-driver-autoupdate.timer` → `~/.local/bin/cua-driver-autoupdate`, log `~/.local/state/cua-driver-autoupdate/autoupdate.log` | Replaces only a slot named exactly `releases/<version>-<target>`. Our `…-main-<sha>-…` slot is logged as `ineligible` and never overwritten. |
| Hyprland plugin | `~/.config/hypr/cua.lua` loads `~/.local/lib/cua/hyprland/0.38.0-seat-lifetime-r2-hyprland-0.56.2/cua-hyprland-plugin.so` | Built from the same branch (plugin source unchanged since `1585ab467`) for the host's Hyprland 0.56.2. Loaded, `seat_lifetime` `session`. Previous module kept for rollback: `0.38.0-seat-lifetime-hyprland-0.56.2` (r1). Install the driver and plugin as a pair: `~/.local/libexec/cua-seat-lifetime/activate` (`check`, `driver`, `plugin`, `verify`, `rollback`). |

## Divergence from upstream

Find the current divergence from source, not from this table:

```bash
git remote add upstream https://github.com/trycua/cua.git   # once; fetch-only
git remote set-url --push upstream DISABLED                 # never push upstream directly
git fetch upstream main && git fetch origin
git log --oneline upstream/main..origin/main                # fork-only commits on main
git diff --stat upstream/main...origin/main
gh pr list -R trycua/cua --author chrisohearn --state open  # our upstream PRs
```

### On `main`

Only docs: `FORK.md` and the `<!-- fork:start -->`…`<!-- fork:end -->` block at the end of `AGENTS.md`.
No product, config or CI file differs from upstream.

### In the installed host build (`host/hyprland-seat-lifetime-0.56.2`, commit `6e5a0cd9d`)

Installed 2026-11-09. It is the `86e6db71c` build below plus session-lifetime
Hyprland agent seats ([trycua/cua#4257](https://github.com/trycua/cua/issues/4257) item 2).
It supersedes closed fork PR #26 (`e3c0769d1`); that PR targeted `main` by mistake.
The plugin advertises a lane's `Cua-Agent` `wl_seat` only while an isolated-input
session uses it, so GPUI apps (Zed, Flea) keep the user's seat when no agent works.
The driver orders seats by `wl_seat` version when it picks the primary seat.
Evidence: 210 Rust Wayland tests, 25 plugin unit tests, 628 Python tests; after
login, one `wl_seat` (`Hyprland`) is visible while idle. Live background-input
acceptance was skipped: the driver qualifies only libreoffice-fresh 26.2.5-3 and
inkscape 1.4.4-6, and neither is installed.

### In the previous host build (`host/cua-semantic-throughput-9350d041`, commit `86e6db71c`)

The host branch combines fork main `9ab99152f`, the previous installed
`host/cua-driver-deep-replies` build (`260833cfc`), and the two contributor-authored
commits from upstream PR #5387. The previous build contains
`feat/cua-headless-isolated-5156e71a` (`d834330d0`) plus the deep-CDP-reply fix.
Build only from the remote host branch.
`feat/cua-headless-isolated-5156e71a` is the head branch of PR #4934, so never push
host-only fixes to it; they would join that PR. Cherry-pick them onto the host branch instead.
Local `up/*` branches in shared clones are other sessions' scratch work.

**1. Existing-profile browser setup on Hyprland ([trycua/cua#4931](https://github.com/trycua/cua/pull/4931), branch `fix/hyprland-existing-profile-5156e71a`).**
Attaches the browser tools to an already-running, signed-in Chrome on Hyprland.
The driver accepts Chrome's remote-debugging consent through AT-SPI, binds the
exact window by scaled size, and hands back focus, workspace and pointer only
when it can show that nobody touched the keyboard or mouse. Use it on the host
daemon only when an isolated profile cannot do the task, and only when Chris asks.
It briefly moves his focus when Chrome shows its consent prompt.

```text
# Host daemon already runs unrestricted with --dangerously-bypass-approvals,
# so no extra grant is needed there. Elsewhere start with:  cua-driver mcp --grant existing-profile
cua-driver call browser_prepare \
  '{"pid":<chrome pid>,"window_id":<window id>,"session":"<label>","strategy":{"kind":"existing_profile"}}' \
  --socket ~/.cache/cua-driver/cua-driver.sock
cua-driver call get_browser_state '{"pid":<chrome pid>,"window_id":<window id>,"session":"<label>"}' \
  --socket ~/.cache/cua-driver/cua-driver.sock
```

Get `pid` and `window_id` from `cua-driver call list_windows '{"app":"Google Chrome"}' --socket …`.
The full contract is in `libs/cua-driver/rust/Skills/cua-driver/BROWSER.md` (section "Existing profile").
Until #4934 merges, its "Driver-owned headless browser" section exists only on the build branch.

**2. Driver-owned headless browser ([trycua/cua#4934](https://github.com/trycua/cua/pull/4934), stacked on #4931).**
Adds `"headless":true` to an `isolated_new` `browser_prepare`. The driver launches
Chromium with `--headless=new` and needs no display, window, focus or input.
Use it for page work that needs no signed-in profile.

```bash
S="$XDG_RUNTIME_DIR/agent-desktop/cua.sock"
cua-driver call browser_prepare \
  '{"session":"hl-demo","allow_launch":true,"headless":true,"profile":{"mode":"isolated_new"}}' --socket "$S"
# → attachment.headless_target, e.g. "hl-…"
cua-driver call get_browser_state '{"session":"hl-demo","headless_target":"<headless_target>"}' --socket "$S"
# → binding_route "driver_owned_headless", target_id, tabs[].tab_id
cua-driver call browser_navigate \
  '{"session":"hl-demo","target_id":"<target_id>","tab_id":"<tab_id>","url":"https://example.com/"}' --socket "$S"
cua-driver call end_session '{"session":"hl-demo"}' --socket "$S"   # kills the browser, deletes the profile
```

Repeat the same `session` label on every call; the anchor works only for the
session that prepared it. Each `get_browser_state` mints fresh `target_id` and
`tab_id` values, so use the ones from the latest call. Click with
`"input_route":"dom_event"`, because there is no screen. `headless` is refused
with `isolated_named`, `existing_profile`, `pid`, `window_id`, or without `allow_launch`.

**3. Deep CDP replies ([trycua/cua#6338](https://github.com/trycua/cua/pull/6338), branch `fix/cdp-deep-dom-replies`).**
`get_browser_state` no longer stalls for 20 s on pages deeper than about 63 elements,
such as ChatGPT. Why: serde_json's default 128-level limit rejected full-depth
`DOM.getDocument` replies, and the CDP reader dropped them until the call timed out.

**4. Target-scoped accessibility identities and cycle guards ([trycua/cua#5387](https://github.com/trycua/cua/pull/5387), author Iflaqbhat).**
Reuses contributor commits `2df642763` and `17b9a45ac`. Accessibility node ids are
scoped to their CDP target, same-process iframe ancestry is retained, and outline
parent walks terminate on cycles. The old host daemon was stuck in those walks,
consuming approximately six logical CPU cores. The installed build preserves the
three existing host features above.

Local verification: 16 semantic tests and the full browser suite (256 passed, one
ignored), release build with `portal-input`, configured source review, and six
isolated headless browsers completing 120 iframe snapshots. Both live daemon
sockets were verified after the pointer switch; shared Chrome was not restarted.
This is host-install evidence, not full cross-platform certification. Broader
qualification includes [a Wayland native evidence-capture timeout](https://github.com/chrisohearn/cua/actions/runs/42133054473); do not treat that run as passing.

### Open upstream PRs not in the host build

These fork branch names start with `upstream/`, so they look like refs on the
`upstream` remote. They are not: check them out as `origin/upstream/<name>`.

| PR | Fork branch | What it fixes |
| --- | --- | --- |
| [trycua/cua#6253](https://github.com/trycua/cua/pull/6253) | `origin/upstream/hyprland-input-api-detect` | Hyprland plugin detects input internals instead of pinning 0.56.2. Needed to load the plugin on Hyprland 0.57. |
| [trycua/cua#6254](https://github.com/trycua/cua/pull/6254) | `origin/upstream/keyvault-upsert-commit-cleanup` | Keyvault keeps payloads consistent when a batch commit fails. |
| [trycua/cua#6255](https://github.com/trycua/cua/pull/6255) | `origin/upstream/qemu-registry-layers` | Sandbox keeps registry identity for QEMU image layers. |
| [trycua/cua#6256](https://github.com/trycua/cua/pull/6256) (draft) | `origin/contrib/ponytail-cleanup-20261031` | Shares benchmark handlers and trims teleport dependencies. |

### Fork repository settings

- **Scheduled workflows are disabled** (51 of them, via the API). Why: upstream's
  nightlies and image rebuilds burned fork compute and made GitHub disable Actions
  on this fork on 2026-10-31. Push and pull-request workflows stay enabled,
  except the next three.
- **Three upstream-credential workflows are disabled** (via the API, 2026-11-03).
  They can only fail here because the fork lacks upstream's credentials, so their
  red runs carry no signal:
  - `release-on-merge.yml` and `release-please.yml`: no `RELEASE_APP_ID` app secret.
  - `cd-docs-pin-dispatch.yml`: upstream's AWS OIDC role refuses the fork.

  Leave other push and pull-request workflows enabled. Their failures on the fork
  are real test results. Fork issues opened by `report-schedule-failure` for an
  image workflow belong upstream once the fork's `main` matches upstream; fork
  issue #11 was closed for that reason, and upstream tracks it in trycua/cua#4806.
- **Issues are enabled.** Upstream issues stay on `trycua/cua`; fork issues track fork-only work.
- **Extra branches:** `archive/fork-main-20261031` (old fork `main`, keep);
  `image-doctor-ledger` (Image Doctor evidence that CI reads, keep in sync with
  upstream's); `cla-signatures` (copy of upstream's CLA bot branch).

## Build, install, test and verify

### Build the host driver

Cargo lives in `~/.cargo/bin`, which is not on the default `PATH`. The toolchain
is pinned by `libs/cua-driver/rust/rust-toolchain.toml` (1.97.1). Build in a
separate worktree, never in the main checkout:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
git fetch origin
# First time:
git worktree add --detach ~/.cache/cua-host-build origin/host/cua-semantic-throughput-9350d041
# Later rebuilds, when the worktree already exists:
git -C ~/.cache/cua-host-build checkout --detach origin/host/cua-semantic-throughput-9350d041
cd ~/.cache/cua-host-build/libs/cua-driver/rust
cargo build --locked -p cua-driver -p cursor-theme-cli --release --features cua-driver/portal-input
target/release/cua-driver --version        # cua-driver 0.38.0
```

This mirrors the Linux release job in `.github/workflows/cd-rust-cua-driver.yml`.
`portal-input` is the feature ordinary Linux releases ship with. The job also
builds `cua-driver-sdk` and passes `--target`. The host install needs neither,
because the daemons use only `cua-driver`, `cua-cursor-theme` and `wayland-helper`. A cold build takes about 1.5 minutes on this machine.

### Test

Plain `cargo test` is hermetic (see `AGENTS.md`, "Cua Driver test ownership").
Focused tests for our two changes, run from `libs/cua-driver/rust`:

```bash
cargo test --locked -p cua-driver-core --lib browser::
cargo test --locked -p platform-linux --features portal-input --lib browser_setup_ui
```

The full `platform-linux` suite needs `Xvfb` for
`input::own_dialog_tests::focus_restore_leaves_focus_on_a_dialog_the_app_opened`.
`Xvfb` is not installed on this host, so that one test fails here on upstream too.
For the plugin, build against the installed Hyprland headers (`pkg-config --modversion hyprland`).
Run this from the repository root of an `origin/upstream/hyprland-input-api-detect` worktree:

```bash
cd libs/cua-driver/hyprland-plugin
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCUA_HYPRLAND_INPUT=ON -DBUILD_TESTING=ON
cmake --build build && ctest --test-dir build --output-on-failure
```

On upstream `main` this configure step stops with `Input is pinned to Hyprland 0.56.2`
on a 0.57 host. Use `origin/upstream/hyprland-input-api-detect` until #6253 merges.
Installing the plugin means copying `build/cua-hyprland-plugin.so` to a new
`~/.local/lib/cua/hyprland/<driver version>-hyprland-<hyprland version>/` directory
and pointing `~/.config/hypr/cua.lua` at it. That edits Hyprland config, so do it
only when Chris asks, and follow the stream-lease rule below first.

### Install a new host build

This changes the live daemons, so do it only when Chris asks for a driver update.
Name the slot `<version>-main-<short sha>-<target>`. Why: any label between the version and
the target keeps `cua-driver-autoupdate` from replacing the custom build with a stock release.
The older `0.35.4-hyprland-811d8cd4` slot used a different label for the same reason.

```bash
cd ~/.cache/cua-host-build/libs/cua-driver/rust
PKG="$HOME/.cua-driver/packages"
SLOT="$(cat VERSION)-main-$(git rev-parse --short=7 HEAD)-x86_64-unknown-linux-gnu"
mkdir -p "$PKG/releases/$SLOT"
install -m755 target/release/cua-driver target/release/cua-cursor-theme "$PKG/releases/$SLOT/"
cp -R ../wayland-helper "$PKG/releases/$SLOT/wayland-helper"
ln -sfn "releases/$SLOT" "$PKG/current.new" && mv -Tf "$PKG/current.new" "$PKG/current"
systemctl --user restart cua-driver.service agent-desktop-cua.service
```

Keep the previous slot. To roll back, point `current` at it the same way and restart both services.

Before you install or load a Hyprland plugin, or edit or reload Hyprland config,
check for an active stream lease (`/run/user/1000/vibepollo-virtual/lease.json`
and the Virtual-1 monitor state). If a lease exists or its state is unclear,
defer. Why: a reload on 2026-10-09 stranded the Vibepollo Virtual-1 stream.

### Verify (read-only)

```bash
cua-driver --version
readlink ~/.cua-driver/packages/current
systemctl --user is-active cua-driver.service agent-desktop-cua.service agent-desktop.target
cua-driver call get_screen_size '{}' --socket ~/.cache/cua-driver/cua-driver.sock
cua-driver call get_screen_size '{}' --socket "$XDG_RUNTIME_DIR/agent-desktop/cua.sock"   # width 1600
agent-desktop doctor
tail -3 ~/.local/state/cua-driver-autoupdate/autoupdate.log
hyprctl plugin list
```

## Sync from upstream

`main` is upstream plus the commit that adds this guide, so sync by merging, never by resetting.
Push a clean sync merge straight to `main`; it adds no fork content, so it needs no PR.
Any change to fork content, such as this guide, goes through a PR.

```bash
git fetch upstream main && git fetch origin main
git switch -c sync/upstream-$(date +%Y%m%d) origin/main
git merge --no-edit upstream/main
git diff --stat upstream/main          # must list only FORK.md and AGENTS.md
git push origin HEAD:main
```

- Do not use `gh repo sync --force` or the "Discard commits" button. Both drop `FORK.md`.
- Only the end of `AGENTS.md` can conflict. Keep upstream's text and re-append the
  `<!-- fork:start -->`…`<!-- fork:end -->` block unchanged as the last lines.
- After every push to `main`, disable any scheduled workflow GitHub newly registered.
  The first command must print nothing:

```bash
gh api --paginate 'repos/chrisohearn/cua/actions/workflows?per_page=100' \
  --jq '.workflows[] | select(.state=="active") | .path' |
  while read -r p; do git show origin/main:"$p" 2>/dev/null | grep -q '^\s*schedule:' && echo "$p"; done
gh workflow disable <workflow-file-name.yml> -R chrisohearn/cua    # for each path printed
```

To refresh the host build after a sync, fetch upstream and origin, then start a
new worktree from `origin/host/cua-semantic-throughput-9350d041` and merge
`upstream/main` there. Preserve the existing-profile, headless, deep-reply and
semantic-identity changes until their replacements are present upstream. Do not
reset or add host integration commits to the branches backing upstream PRs.
Run the focused tests, push the host branch, rebuild and install as above.
When #4931, #4934, #6338 and #5387 ship in a component release, verify the stock
installer contains their behavior before retiring the custom slot.

## Working rules for this fork

- **Fork-only work** (this guide, fork settings): open the PR against `chrisohearn/cua` `main`.
- **Product fixes:** branch from `upstream/main` and push to `origin`. Open the PR on
  `trycua/cua` with `--head chrisohearn:<branch>`. This overrides upstream `AGENTS.md`'s
  "push in the canonical repository" default, because we lack write access there.
- **Keep upstream files as they are.** Do not restructure upstream docs; every sync would conflict.
  Put fork notes in `FORK.md`.
- **Follow upstream rules for upstream PRs:** Conventional Commit titles, contributor
  authorship, and the security process in `.github/SECURITY.md`.

## Upstream docs that stay authoritative

| Read when… | File |
| --- | --- |
| choosing where work starts, PR titles, release labels, CLA | `.github/CONTRIBUTING.md` |
| polling or selecting upstream work | `docs/contributing/MAINTAINERS.md` |
| finding which component owns a path or toolchain | `docs/contributing/Development.md` |
| choosing test commands or CI workflows | `docs/contributing/TESTING.md`, `.github/workflows/README.md` |
| running pre-push checks | `scripts/ci/prepush.sh` (`--fast` for docs-only) |
| changing Cua Driver behavior | `libs/cua-driver/README.md`, `libs/cua-driver/docs/test-harnesses-guide.md` |
| using browser tools (profiles, headless, consent) | `libs/cua-driver/rust/Skills/cua-driver/BROWSER.md` |
| working on Linux, X11 or Wayland support | `libs/cua-driver/rust/Skills/cua-driver/LINUX.md` |
| building or requalifying the Hyprland plugin | `libs/cua-driver/hyprland-plugin/README.md`, `libs/cua-driver/hyprland-plugin/requalify/COMPAT-BRANCH.md` |
| running the desktop E2E matrix | `scripts/ci/README.md` ("Desktop runners") |
| suspecting a vulnerability | `.github/SECURITY.md` (private reporting only) |
