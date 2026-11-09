"""Exercise the session-seat wait and withdrawal decisions with production bodies.

`resume_pending` and `retire_idle_seat` come from input_experiment.cpp, so a
changed production call site changes the behavior under test. The seat
lifetime is the real AgentSeatLifetime; Wayland resources, the action path and
withdrawal are fakes that only record calls. This is policy coverage for #4257,
not evidence that a client binds a new seat or that Hyprland delivers input.
"""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include "agent_seat_lifetime.hpp"

#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <string>
#include <vector>

using namespace cua::hyprland;
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
constexpr bool kSessionSeats = true;
std::string refusal(const char* code) { return code; }
void check(bool ok, const char* why) {
    if (!ok) { std::cerr << "FAIL: " << why << '\n'; std::exit(1); }
}

struct Client { bool dead = false; };
struct PendingAction { Client* client; std::vector<std::string> fields; std::uint64_t capability; };
struct Global {};

struct Lane {
    AgentSeatLifetime<Global*> seat_lifetime;
    std::optional<PendingAction> pending;
    Client* lease = nullptr;
    Client* reservation = nullptr;
    bool drag = false, retired = false, suspended = false, bound = false, throws = false;
    unsigned held_button = 0, withdrawals = 0;
    std::vector<unsigned> held_keys;
    std::vector<std::string> actions, sent, revoked;
    Global global;

    bool target_bound(const Client&, std::uint64_t) const { return bound; }
    void action(Client&, const std::vector<std::string>& f, std::uint64_t) {
        if (throws) throw 1;
        actions.push_back(f.front());
    }
    void revoke(const char* reason) { revoked.push_back(reason); }
    void send(Client&, const std::string& packet) { sent.push_back(packet); }
    void withdraw_seat() { ++withdrawals; seat_lifetime.withdraw(Clock::now()); }
    // PRODUCTION_METHODS
};

int main() {
    Client owner;
    const auto park = [&](Lane& l) {
        l.lease = l.reservation = &owner;
        l.seat_lifetime.publish(&l.global, Clock::now());
        l.pending.emplace(PendingAction{&owner, {"KEY"}, 2});
    };
    {   // Unbound inside the window: keep waiting, reply nothing.
        Lane l; park(l);
        l.resume_pending(Clock::now());
        check(l.pending && l.actions.empty() && l.sent.empty(), "waits while the target has not bound");
        // The target binds: the held action runs once.
        l.bound = true;
        l.resume_pending(Clock::now());
        check(!l.pending && l.actions == std::vector<std::string>{"KEY"}, "bound target resumes the held action");
    }
    {   // The window passes without a bind: the action re-runs to refuse.
        Lane l; park(l);
        l.resume_pending(Clock::now() + AgentSeatLifetime<Global*>::bind_window);
        check(!l.pending && l.actions.size() == 1, "deadline re-enters the action path to refuse");
    }
    {   // An owner that lost its lease or died is dropped without input.
        Lane l; park(l); l.lease = nullptr; l.bound = true;
        l.resume_pending(Clock::now());
        check(!l.pending && l.actions.empty(), "lost lease drops the held action");
        Lane d; park(d); owner.dead = true; d.bound = true;
        d.resume_pending(Clock::now());
        check(!d.pending && d.actions.empty(), "dead owner drops the held action");
        owner.dead = false;
    }
    {   // An exception while resuming refuses instead of escaping the timer.
        Lane l; park(l); l.bound = true; l.throws = true;
        l.resume_pending(Clock::now());
        check(!l.pending && l.revoked == std::vector<std::string>{"invalid_request"} &&
              l.sent == std::vector<std::string>{"invalid_request"}, "resume failure refuses");
    }
    {   // No published seat: nothing to withdraw.
        Lane l; l.retire_idle_seat(Clock::now());
        check(l.withdrawals == 0, "unpublished seat untouched");
    }
    const auto now = Clock::now();
    const auto idle = now + AgentSeatLifetime<Global*>::idle_timeout;
    {   // A claimed, recently used lane keeps its seat; idleness withdraws it.
        Lane l; l.reservation = &owner; l.seat_lifetime.publish(&l.global, now);
        l.retire_idle_seat(now + 1s);
        check(l.withdrawals == 0, "active session keeps its seat");
        l.retire_idle_seat(idle);
        check(l.withdrawals == 1 && !l.seat_lifetime.published(), "idle lane withdraws its seat");
    }
    for (int busy = 0; busy < 5; ++busy) {
        // Work in progress is never withdrawn for idleness.
        Lane l; l.reservation = &owner; l.seat_lifetime.publish(&l.global, now);
        switch (busy) {
            case 0: l.lease = &owner; break;
            case 1: l.drag = true; break;
            case 2: l.pending.emplace(PendingAction{&owner, {"CLICK"}, 1}); break;
            case 3: l.held_button = 272; break;
            case 4: l.held_keys.push_back(30); break;
        }
        l.retire_idle_seat(idle);
        check(l.withdrawals == 0, "busy lane kept its seat past the idle timeout");
    }
    for (int ended = 0; ended < 3; ++ended) {
        // A session that ended withdraws at once, without waiting for idleness.
        Lane l; l.reservation = &owner; l.lease = &owner; l.seat_lifetime.publish(&l.global, now);
        if (ended == 0) l.reservation = nullptr;
        if (ended == 1) l.suspended = true;
        if (ended == 2) l.retired = true;
        l.retire_idle_seat(now);
        check(l.withdrawals == 1, "ended session kept its seat");
    }
    std::cout << "seat session policy tests passed\n";
}
'''


def method(source, name):
    match = re.search(r'^    void ' + name + r'\(.*?^    }', source, re.M | re.S)
    if not match:
        raise AssertionError(f'production method not found: {name}')
    return match.group()


class SeatSessionPolicyTest(unittest.TestCase):
    def test_production_wait_and_withdrawal(self):
        source = (ROOT / 'src/input_experiment.cpp').read_text()
        step = method(source, 'step')
        # Fail if the tested decisions are disconnected from the production timer.
        for call in ('resume_pending(Clock::now());', 'retire_idle_seat(Clock::now());',
                     'destroy_withdrawn_seats(Clock::now());'):
            self.assertIn(call, step)
        # A background action parks only behind the bind gate, never the foreground route.
        self.assertRegex(source, r'foreground_request\(c, f, cap\);\n            return;\n        }\n'
                                 r'        if \(kSessionSeats && !target_bound\(c, cap\)\) \{')
        methods = '\n'.join(method(source, name) for name in ('resume_pending', 'retire_idle_seat'))
        compiler = shlex.split(os.environ.get('CXX', '')) or [
            shutil.which('clang++-18') or shutil.which('clang++') or 'c++']
        with tempfile.TemporaryDirectory(prefix='cua-seat-session-policy-') as directory:
            cpp, binary = Path(directory) / 'policy.cpp', Path(directory) / 'policy'
            cpp.write_text(FIXTURE.replace('// PRODUCTION_METHODS', methods))
            build = subprocess.run([*compiler, '-std=c++20', '-Wall', '-Wextra', '-Wpedantic', '-Werror',
                                    '-I', str(ROOT / 'src'), str(cpp), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
