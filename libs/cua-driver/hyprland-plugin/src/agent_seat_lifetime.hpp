#pragma once

#include <chrono>
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
// A withdrawn global stays allocated for `destroy_delay`, so a client that
// binds it before processing global_remove gets an inert seat rather than a
// protocol error.
//
// This class holds only timing and generation policy. It never creates or
// destroys Wayland objects; the caller owns `Handle` and destroys the handles
// that `expired` returns.
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
    // Keep a withdrawn global bindable (inertly) for this long.
    static constexpr auto destroy_delay = std::chrono::seconds(5);

    bool published() const { return published_; }
    std::uint64_t generation() const { return generation_; }
    // The generation the next publication will use.
    std::uint64_t next_generation() const { return generation_ + 1; }
    bool current(std::uint64_t generation) const { return published_ && generation == generation_; }
    const Handle& handle() const { return current_; }

    // Records a global the caller created for next_generation().
    void publish(Handle handle, Clock::time_point now) {
        if (published_) return;
        published_ = true;
        ++generation_;
        current_ = std::move(handle);
        published_at_ = last_use_ = now;
    }
    // Any admission or dispatch keeps a published seat from going idle.
    void touch(Clock::time_point now) {
        if (published_) last_use_ = now;
    }
    // True while a client that has not bound the new seat may still do so.
    bool binding(Clock::time_point now) const { return published_ && now < published_at_ + bind_window; }
    Clock::time_point bind_deadline() const { return published_at_ + bind_window; }
    bool idle(Clock::time_point now) const { return published_ && now - last_use_ >= idle_timeout; }

    // Stops advertising the current generation. The caller must already have
    // removed the global from the registry; the handle waits for `expired`.
    void withdraw(Clock::time_point now) {
        if (!published_) return;
        published_ = false;
        withdrawn_.push_back({std::move(current_), now + destroy_delay});
        current_ = Handle{};
    }
    // Returns the withdrawn handles whose destroy delay has passed.
    std::vector<Handle> expired(Clock::time_point now) {
        std::vector<Handle> result;
        std::erase_if(withdrawn_, [&](auto& entry) {
            if (now < entry.second) return false;
            result.push_back(std::move(entry.first));
            return true;
        });
        return result;
    }
    std::size_t withdrawn() const { return withdrawn_.size(); }

  private:
    bool published_ = false;
    std::uint64_t generation_ = 0;
    Handle current_{};
    Clock::time_point published_at_{}, last_use_{};
    std::vector<std::pair<Handle, Clock::time_point>> withdrawn_;
};
} // namespace cua::hyprland
