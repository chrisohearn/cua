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
    check(seat.withdraw() == 0 && seat.withdrawn() == 0, "withdrawing nothing retains nothing");
    check(!seat.release(0) && seat.teardown().empty(), "nothing to destroy before publication");

    // An admitted session publishes generation 1.
    check(seat.next_generation() == 1, "first publication is generation 1");
    check(seat.publish(11, t0), "first publication accepted");
    check(seat.published() && seat.generation() == 1 && seat.handle() == 11, "publication records the global");
    check(seat.current(1) && !seat.current(0), "only the published generation is current");
    check(!seat.publish(12, t0 + 1s), "republishing a live seat is refused");
    check(seat.generation() == 1 && seat.handle() == 11, "republishing a live seat changes nothing");
    check(!seat.release(11), "the published global is never released");

    // Bounded bind window from publication, not from the latest action.
    check(seat.binding(t0) && seat.binding(t0 + Lifetime::bind_window - 1ms), "bind window open");
    seat.touch(t0 + 1s);
    check(!seat.binding(t0 + Lifetime::bind_window), "bind window closes at its bound");
    check(seat.bind_deadline() == t0 + Lifetime::bind_window, "deadline is publication plus window");

    // Idle is measured from the last use.
    check(!seat.idle(t0 + 1s + Lifetime::idle_timeout - 1ms), "recent use is not idle");
    check(seat.idle(t0 + 1s + Lifetime::idle_timeout), "idle after the timeout");

    // Withdrawal stops the generation at once and retains the global, with no
    // time limit, until libwayland reports it withdrawn.
    check(seat.withdraw() == 11, "withdrawal returns the global to remove");
    check(!seat.published() && !seat.current(1), "withdrawn generation is inert");
    check(!seat.idle(t0 + 1h) && !seat.binding(t0 + 30s), "withdrawn seat has no lifetime");
    check(seat.withdrawn() == 1, "withdrawn global retained");
    check(seat.withdraw() == 0 && seat.withdrawn() == 1, "repeated withdrawal is a no-op");

    // A new session publishes a fresh generation while the old global waits.
    check(seat.publish(21, t0 + 31s), "new session publishes while an old global is retained");
    check(seat.generation() == 2 && seat.current(2) && !seat.current(1), "new session gets a new generation");
    check(seat.binding(t0 + 31s), "new generation reopens the bind window");
    check(!seat.release(21), "the current generation cannot be released");
    check(seat.release(11) && seat.withdrawn() == 0, "released once every registry acknowledged it");
    check(!seat.release(11), "a global is released once");
    check(seat.handle() == 21 && seat.published(), "current global untouched by release");

    // Releases may arrive in any order (one client acks late).
    check(seat.withdraw() == 21, "second withdrawal");
    check(seat.publish(31, t0 + 40s) && seat.withdraw() == 31, "third generation withdrawn");
    check(seat.withdrawn() == 2, "both withdrawn globals retained");
    check(seat.release(31) && seat.withdrawn() == 1, "a later generation can be released first");
    check(seat.generation() == 3 && !seat.published(), "generations never repeat");

    // Teardown returns every remaining handle, current and withdrawn.
    check(seat.publish(41, t0 + 50s), "fourth generation");
    auto remaining = seat.teardown();
    check(remaining == std::vector<int>{21, 41}, "teardown returns withdrawn and current globals");
    check(!seat.published() && seat.withdrawn() == 0 && seat.teardown().empty(), "teardown empties the lifetime");
    check(seat.next_generation() == 5, "teardown never reuses a generation");

    // Retention is bounded. At the cap no new generation is published, and a
    // single release makes room again.
    Lifetime bounded;
    for (std::size_t i = 0; i < Lifetime::max_withdrawn; ++i) {
        check(bounded.publish(static_cast<int>(i + 1), t0), "publication below the cap");
        check(bounded.withdraw() == static_cast<int>(i + 1), "withdrawal below the cap");
    }
    check(bounded.exhausted() && bounded.withdrawn() == Lifetime::max_withdrawn, "cap reached");
    check(!bounded.publish(9999, t0) && !bounded.published(), "publication refused at the cap");
    check(bounded.generation() == Lifetime::max_withdrawn, "a refused publication consumes no generation");
    check(bounded.release(7) && !bounded.exhausted(), "a release makes room");
    check(bounded.publish(9999, t0) && bounded.current(Lifetime::max_withdrawn + 1), "publication resumes");
    check(bounded.teardown().size() == Lifetime::max_withdrawn, "teardown returns every retained global");

    // The wait fits inside Driver's request deadline and the action grant.
    static_assert(Lifetime::bind_window < std::chrono::seconds(3));
    static_assert(Lifetime::idle_timeout < std::chrono::seconds(60));
    static_assert(Lifetime::max_withdrawn > 0);
    std::cout << "agent seat lifetime tests passed\n";
}
