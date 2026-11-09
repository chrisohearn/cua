#include "agent_seat_lifetime.hpp"

#include <cstdlib>
#include <iostream>

namespace {
void check(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
using Lifetime = cua::hyprland::AgentSeatLifetime<int>;
using namespace std::chrono_literals;
}

int main() {
    const Lifetime::Clock::time_point t0{};
    Lifetime seat;

    // No agent session: nothing is advertised and no generation is current.
    check(!seat.published() && seat.generation() == 0, "starts unpublished");
    check(!seat.current(0) && !seat.binding(t0) && !seat.idle(t0 + 1h), "unpublished seat has no lifetime");
    check(seat.expired(t0 + 1h).empty(), "nothing to destroy before publication");

    // An admitted session publishes generation 1.
    check(seat.next_generation() == 1, "first publication is generation 1");
    seat.publish(11, t0);
    check(seat.published() && seat.generation() == 1 && seat.handle() == 11, "publication records the global");
    check(seat.current(1) && !seat.current(0), "only the published generation is current");
    seat.publish(12, t0 + 1s);
    check(seat.generation() == 1 && seat.handle() == 11, "republishing a live seat is a no-op");

    // Bounded bind window from publication, not from the latest action.
    check(seat.binding(t0) && seat.binding(t0 + Lifetime::bind_window - 1ms), "bind window open");
    seat.touch(t0 + 1s);
    check(!seat.binding(t0 + Lifetime::bind_window), "bind window closes at its bound");
    check(seat.bind_deadline() == t0 + Lifetime::bind_window, "deadline is publication plus window");

    // Idle is measured from the last use.
    check(!seat.idle(t0 + 1s + Lifetime::idle_timeout - 1ms), "recent use is not idle");
    check(seat.idle(t0 + 1s + Lifetime::idle_timeout), "idle after the timeout");

    // Withdrawal stops the generation immediately and delays destruction.
    const auto withdrawn_at = t0 + 30s;
    seat.withdraw(withdrawn_at);
    check(!seat.published() && !seat.current(1), "withdrawn generation is inert");
    check(!seat.idle(withdrawn_at + 1h) && !seat.binding(withdrawn_at), "withdrawn seat has no lifetime");
    check(seat.withdrawn() == 1, "withdrawn global retained");
    check(seat.expired(withdrawn_at + Lifetime::destroy_delay - 1ms).empty(), "global kept bindable during delay");
    seat.withdraw(withdrawn_at + 1s);
    check(seat.withdrawn() == 1, "repeated withdrawal is a no-op");

    // A new session publishes a fresh generation while the old global waits.
    seat.publish(21, withdrawn_at + 1s);
    check(seat.generation() == 2 && seat.current(2) && !seat.current(1), "new session gets a new generation");
    check(seat.binding(withdrawn_at + 1s), "new generation reopens the bind window");
    auto destroyed = seat.expired(withdrawn_at + Lifetime::destroy_delay);
    check(destroyed.size() == 1 && destroyed.front() == 11, "old global destroyed after the delay");
    check(seat.withdrawn() == 0 && seat.handle() == 21, "current global untouched by expiry");

    seat.withdraw(withdrawn_at + 2s);
    seat.publish(31, withdrawn_at + 3s);
    seat.withdraw(withdrawn_at + 4s);
    destroyed = seat.expired(withdrawn_at + 2s + Lifetime::destroy_delay);
    check(destroyed.size() == 1 && destroyed.front() == 21, "expiry is per withdrawal");
    destroyed = seat.expired(withdrawn_at + 1h);
    check(destroyed.size() == 1 && destroyed.front() == 31 && seat.withdrawn() == 0, "all withdrawn globals expire");
    check(seat.generation() == 3 && !seat.published(), "generations never repeat");

    // The wait fits inside Driver's request deadline and the action grant.
    static_assert(Lifetime::bind_window < std::chrono::seconds(3));
    static_assert(Lifetime::idle_timeout < std::chrono::seconds(60));
    std::cout << "agent seat lifetime tests passed\n";
}
