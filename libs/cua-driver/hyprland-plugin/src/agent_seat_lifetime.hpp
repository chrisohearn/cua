#pragma once

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace cua::hyprland {
// Lifetime of one lane's advertised wl_seat global (#4257). A production lane
// publishes its seat only while an admitted isolated-input session uses it, so
// a client that keeps the last advertised wl_seat (GPUI/Zed, imv) sees only
// the user's seat while no agent is working.
//
// Each publication is a new generation. Resources bound to an older
// generation stay valid but inert: libwayland cannot revoke client-owned
// objects, and destroying them disconnects clients that later send requests.
// A withdrawn global stays allocated until libwayland reports that no more
// bind requests can arrive for it (every registry that was offered it has
// acknowledged the removal through wl_fixes or been destroyed). Without that
// report it stays allocated until plugin teardown. No timeout is treated as
// proof that a slow client has processed global_remove.
//
// This class holds only timing, generation and retention policy. It never
// creates or destroys Wayland objects; the caller owns `Handle` and destroys
// the handles that `release` accepts or `teardown` returns.
template <class Handle>
class AgentSeatLifetime {
  public:
    using Clock = std::chrono::steady_clock;
    // The first isolated action on a new seat waits at most this long for the
    // target client to bind it, then refuses. It never uses the user's seat.
    // Driver's per-request deadline (3 s) and the 5 s action grant both cover it.
    static constexpr auto bind_window = std::chrono::milliseconds(1500);
    // A claimed lane with no action for this long withdraws its seat. The next
    // admitted action republishes it and waits for the target to bind again.
    static constexpr auto idle_timeout = std::chrono::seconds(20);
    // Withdrawn globals a lane retains while it waits for registries to
    // acknowledge them. At the bound, publication refuses: a client that never
    // acknowledges removals cannot grow compositor memory without limit, and
    // the lane never falls back to the user's seat.
    static constexpr std::size_t max_withdrawn = 1024;

    bool published() const { return published_; }
    std::uint64_t generation() const { return generation_; }
    // The generation the next publication will use.
    std::uint64_t next_generation() const { return generation_ + 1; }
    bool current(std::uint64_t generation) const { return published_ && generation == generation_; }
    const Handle& handle() const { return current_; }
    // True when no new generation may be published until a withdrawn global
    // is released.
    bool exhausted() const { return withdrawn_.size() >= max_withdrawn; }

    // Records a global the caller created for next_generation(). Returns false
    // and records nothing when a seat is already published or retention is
    // exhausted; the caller then destroys `handle` itself.
    bool publish(Handle handle, Clock::time_point now) {
        if (published_ || exhausted()) return false;
        published_ = true;
        ++generation_;
        current_ = std::move(handle);
        published_at_ = last_use_ = now;
        return true;
    }
    // Any admission or dispatch keeps a published seat from going idle.
    void touch(Clock::time_point now) {
        if (published_) last_use_ = now;
    }
    // True while a client that has not bound the new seat may still do so.
    bool binding(Clock::time_point now) const { return published_ && now < published_at_ + bind_window; }
    Clock::time_point bind_deadline() const { return published_at_ + bind_window; }
    bool idle(Clock::time_point now) const { return published_ && now - last_use_ >= idle_timeout; }

    // Stops advertising the current generation and returns its handle, now
    // retained as withdrawn. Call this BEFORE wl_global_remove: libwayland
    // reports a global that no registry was offered as withdrawn from inside
    // wl_global_remove, and `release` must already find it. Returns Handle{}
    // when nothing is published.
    Handle withdraw() {
        if (!published_) return Handle{};
        published_ = false;
        withdrawn_.push_back(current_);
        return std::exchange(current_, Handle{});
    }
    // Forgets a withdrawn handle once libwayland reports that no more binds
    // can arrive. Returns false for the current or an unknown handle, which
    // the caller must then not destroy.
    bool release(const Handle& handle) {
        const auto found = std::ranges::find(withdrawn_, handle);
        if (found == withdrawn_.end()) return false;
        withdrawn_.erase(found);
        return true;
    }
    // Plugin teardown: every handle the lifetime still holds, current and
    // withdrawn, leaving it unpublished and empty. Generations never repeat.
    std::vector<Handle> teardown() {
        std::vector<Handle> result = std::move(withdrawn_);
        withdrawn_.clear();
        if (published_) result.push_back(std::exchange(current_, Handle{}));
        published_ = false;
        return result;
    }
    std::size_t withdrawn() const { return withdrawn_.size(); }

  private:
    bool published_ = false;
    std::uint64_t generation_ = 0;
    Handle current_{};
    Clock::time_point published_at_{}, last_use_{};
    std::vector<Handle> withdrawn_;
};
} // namespace cua::hyprland
