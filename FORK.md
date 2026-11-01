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
| Installed driver | `~/.cua-driver/packages/current` → `releases/0.38.0-main-d834330-x86_64-unknown-linux-gnu` | Built from fork commit `d834330d0`. Previous build kept: `releases/0.35.4-hyprland-811d8cd4-x86_64-unknown-linux-gnu`. |
| `cua-driver` on `PATH` | `~/.local/bin/cua-driver` → `~/.cua-driver/packages/current/cua-driver` | Every consumer below resolves the binary through this symlink. |
| Host daemon | `cua-driver.service` (`~/.config/systemd/user/cua-driver.service`) | `cua-driver serve --permission-mode unrestricted --dangerously-bypass-approvals`, `CUA_DRIVER_RS_ENABLE_WAYLAND=1`. Socket `~/.cache/cua-driver/cua-driver.sock`. Drives Chris's own screen; use it only when he asks. |
| Agent desktop daemon | `agent-desktop-cua.service`, part of `agent-desktop.target` | `agent-desktop run cua` starts `cua-driver serve --socket $XDG_RUNTIME_DIR/agent-desktop/cua.sock … --no-overlay` on invisible display `:42`. Agents do all browser work here. |
| Agent desktop product | Repo `Revotech-Networks/agent-desktop`, checkout `~/Developer/Revotech/Projects/agent-desktop`, installed at `~/.local/share/agent-desktop/app/agent-desktop` (`~/.local/bin/agent-desktop`) | Overrides the driver path with `AGENT_DESKTOP_CUA`; defaults to `~/.local/bin/cua-driver`. |
| MCP clients | Claude Code user MCP server `agent-desktop`; Codex `[mcp_servers.agent_desktop]` in `~/.codex/config.toml` | Both run `cua-driver mcp --socket $XDG_RUNTIME_DIR/agent-desktop/cua.sock`. |
| Auto-update | `cua-driver-autoupdate.timer` → `~/.local/bin/cua-driver-autoupdate`, log `~/.local/state/cua-driver-autoupdate/autoupdate.log` | Replaces only a slot named exactly `releases/<version>-<target>`. Our `…-main-<sha>-…` slot is logged as `ineligible` and never overwritten. |
| Hyprland plugin | `~/.config/hypr/cua.lua` loads `~/.local/lib/cua/hyprland/0.34.0-hyprland-0.56.2/cua-hyprland-plugin.so` | Not loaded: the host runs Hyprland 0.57.0 and the module was built for 0.56.2 (`hyprctl plugin list` → `no plugins loaded`). The fix is upstream PR #6253. |

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

### In the installed host build (`feat/cua-headless-isolated-5156e71a`, commit `d834330d0`)

That commit merges upstream `d1fe368a6` with two stacked upstream PRs. The PR
branch is also the integration branch for the host build.

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

### Open upstream PRs not in the host build

| PR | Fork branch | What it fixes |
| --- | --- | --- |
| [trycua/cua#6253](https://github.com/trycua/cua/pull/6253) | `upstream/hyprland-input-api-detect` | Hyprland plugin detects input internals instead of pinning 0.56.2. Needed to load the plugin on Hyprland 0.57. |
| [trycua/cua#6254](https://github.com/trycua/cua/pull/6254) | `upstream/keyvault-upsert-commit-cleanup` | Keyvault keeps payloads consistent when a batch commit fails. |
| [trycua/cua#6255](https://github.com/trycua/cua/pull/6255) | `upstream/qemu-registry-layers` | Sandbox keeps registry identity for QEMU image layers. |
| [trycua/cua#6256](https://github.com/trycua/cua/pull/6256) (draft) | `contrib/ponytail-cleanup-20261031` | Shares benchmark handlers and trims teleport dependencies. |

### Fork repository settings

- **Scheduled workflows are disabled** (51 of them, via the API). Why: upstream's
  nightlies and image rebuilds burned fork compute and made GitHub disable Actions
  on this fork on 2026-10-31. Push and pull-request workflows stay enabled.
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
git worktree add --detach ~/.cache/cua-host-build origin/feat/cua-headless-isolated-5156e71a
cd ~/.cache/cua-host-build/libs/cua-driver/rust
cargo build --locked -p cua-driver -p cursor-theme-cli --release --features cua-driver/portal-input
target/release/cua-driver --version        # cua-driver 0.38.0
```

This mirrors the Linux release job in `.github/workflows/cd-rust-cua-driver.yml`.
`portal-input` is the feature ordinary Linux releases ship with. A cold build takes about 1.5 minutes on this machine.

### Test

Plain `cargo test` is hermetic (see `AGENTS.md`, "Cua Driver test ownership").
Focused tests for our two changes:

```bash
cargo test --locked -p cua-driver-core --lib browser::
cargo test --locked -p platform-linux --features portal-input --lib browser_setup_ui
```

The full `platform-linux` suite needs `Xvfb` for
`input::own_dialog_tests::focus_restore_leaves_focus_on_a_dialog_the_app_opened`.
`Xvfb` is not installed on this host, so that one test fails here on upstream too.
For the plugin, build against the installed Hyprland headers (`pkg-config --modversion hyprland`):

```bash
cd libs/cua-driver/hyprland-plugin
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCUA_HYPRLAND_INPUT=ON -DBUILD_TESTING=ON
cmake --build build && ctest --test-dir build --output-on-failure
```

On upstream `main` this configure step stops with `Input is pinned to Hyprland 0.56.2`
on a 0.57 host. Use the `upstream/hyprland-input-api-detect` branch until #6253 merges.

### Install a new host build

This changes the live daemons, so do it only when Chris asks for a driver update.
Name the slot `<version>-main-<short sha>-<target>`. Why: any label between the version and
the target keeps `cua-driver-autoupdate` from replacing the custom build with a stock release.

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

`main` is upstream plus one docs commit, so sync by merging, never by resetting.

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

To refresh the host build after a sync, merge `upstream/main` into
`feat/cua-headless-isolated-5156e71a`. It already contains #4931's commits.
Expect conflicts in the browser consent and existing-profile code under
`libs/cua-driver/rust/crates/platform-linux/src/`. Keep upstream's behavior and
re-apply ours on top. Then run the focused tests, push, rebuild and install as above.
When #4931 and #4934 ship upstream, go back to the stock installer and delete both branches.

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
