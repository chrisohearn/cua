"""Exercise agent seat global destruction and resource limits with production bodies.

publish_seat, withdraw_seat, seat_withdrawn, bind_seat and add_pointer/keyboard/
touch come from input_experiment.cpp, so a changed production body changes the
behavior under test. The seat lifetime is the real AgentSeatLifetime. The
libwayland global calls are fakes that model wl_global_remove and the 1.26
withdrawn listener as documented (synchronous when no registry was offered the
global, otherwise after the last offering registry acknowledges or is
destroyed). This is policy coverage for #4257, not evidence of libwayland or
Hyprland behavior.
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

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

using namespace cua::hyprland;
using Clock = std::chrono::steady_clock;
template <class T> using SP = std::shared_ptr<T>;
template <class T> SP<T> makeShared(auto&&... args) { return std::make_shared<T>(args...); }
template <class T> struct WP { std::weak_ptr<T> value; };
struct CWLSurfaceResource {};
void check(bool ok, const char* why) {
    if (!ok) { std::cerr << "FAIL: " << why << '\n'; std::exit(1); }
}

// libwayland stand-ins.
struct wl_client { int no_memory = 0; };
struct wl_display {};
struct wl_interface {};
struct wl_resource {};
struct wl_global;
wl_interface wl_seat_interface;
using wl_global_bind_func_t = void (*)(wl_client*, void*, std::uint32_t, std::uint32_t);
using wl_global_withdrawn_func_t = void (*)(struct wl_global*);
struct wl_global {
    void* data;
    int offers;  // registries that were offered this global and have not acked
    bool removed = false;
    wl_global_withdrawn_func_t withdrawn = nullptr;
};
int registries = 0, created = 0, destroyed = 0;
std::vector<wl_global*> live;
wl_global* wl_global_create(wl_display*, const wl_interface*, int, void* data, wl_global_bind_func_t) {
    auto* global = new wl_global{data, registries};
    live.push_back(global); ++created;
    return global;
}
void wl_global_remove(wl_global* global) {
    check(!global->removed, "wl_global_remove called twice");
    global->removed = true;
    if (global->withdrawn && global->offers == 0) global->withdrawn(global);
}
// One offering registry acked the removal through wl_fixes or was destroyed.
void registry_done(wl_global* global) {
    check(global->offers > 0, "no offer left to finish");
    if (--global->offers == 0 && global->removed && global->withdrawn) global->withdrawn(global);
}
void wl_global_destroy(wl_global* global) {
    check(std::erase(live, global) == 1, "destroyed an unknown global");
    delete global; ++destroyed;
}
void* wl_global_get_user_data(const wl_global* global) { return global->data; }
void set_withdrawn_listener(wl_global* global, wl_global_withdrawn_func_t func) { global->withdrawn = func; }
// A function pointer, like the weak symbol: null models libwayland < 1.26.
void (*wl_global_set_withdrawn_listener)(wl_global*, wl_global_withdrawn_func_t) = set_withdrawn_listener;
#define CUA_HYPRLAND_GLOBAL_WITHDRAWN_LISTENER 1
void wl_client_post_no_memory(wl_client* client) { ++client->no_memory; }

enum wl_seat_capability { WL_SEAT_CAPABILITY_POINTER = 1, WL_SEAT_CAPABILITY_KEYBOARD = 2 };
constexpr int WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1 = 1;
struct Resource {
    wl_client* owner; std::uint32_t protocol_version; int capabilities = -1;
    Resource(wl_client* client, std::uint32_t version, std::uint32_t) : owner(client), protocol_version(version) {}
    bool resource() const { return true; }
    wl_client* client() const { return owner; }
    std::uint32_t version() const { return protocol_version; }
    void setData(void*) {}
    template <class F> void setRelease(F&&) {}
    template <class F> void setOnDestroy(F&&) {}
    template <class F> void setGetPointer(F&&) {}
    template <class F> void setGetKeyboard(F&&) {}
    template <class F> void setGetTouch(F&&) {}
    template <class F> void setSetCursor(F&&) {}
    void sendName(const char*) {}
    void sendCapabilities(wl_seat_capability value) { capabilities = value; }
    void sendKeymap(int, int, std::size_t) {}
    void sendRepeatInfo(int, int) {}
    void noMemory() { ++owner->no_memory; }
};
struct CWlSeat : Resource { using Resource::Resource; };
struct CWlPointer : Resource { using Resource::Resource; };
struct CWlKeyboard : Resource { using Resource::Resource; };
struct CWlTouch : Resource { using Resource::Resource; };
struct xkb_state {};
xkb_state canonical_state;
struct { wl_display* m_wlDisplay = nullptr; } compositor;
auto* g_pCompositor = &compositor;
constexpr bool kProduction = true;
// PRODUCTION_CONSTANTS

struct Impl {
    // PRODUCTION_STRUCTS
    AgentSeatLifetime<SeatGlobal*> seat_lifetime;
    std::vector<std::unique_ptr<Seat>> seats;
    std::vector<std::unique_ptr<Pointer>> pointers;
    std::vector<std::unique_ptr<Keyboard>> keyboards;
    std::vector<std::unique_ptr<Touch>> touches;
    xkb_state* keyboard_state = &canonical_state;
    int keymap_fd = 3, repeat_rate = 25, repeat_delay = 600;
    std::string keymap_text = "us";
    std::size_t lane = 0;
    bool retired = false;
    int focus_left = 0;
    void leave_pointer() { ++focus_left; }
    void leave_keyboard() {}
    bool current(std::uint64_t generation) const { return seat_lifetime.current(generation); }
    // PRODUCTION_METHODS
    ~Impl() {
        for (auto* record : seat_lifetime.teardown()) { wl_global_destroy(record->global); delete record; }
    }
};
using Lifetime = AgentSeatLifetime<Impl::SeatGlobal*>;

int main() {
    {   // No registry saw the global: libwayland reports it withdrawn from
        // inside wl_global_remove, so the record must already be retained.
        Impl lane; registries = 0;
        check(lane.publish_seat() && live.size() == 1, "seat published");
        lane.withdraw_seat();
        check(live.empty() && destroyed == 1 && lane.seat_lifetime.withdrawn() == 0,
              "an unoffered global is destroyed by the synchronous withdrawn callback");
        check(lane.focus_left == 1 && !lane.seat_lifetime.published(), "withdrawal released agent focus");
    }
    destroyed = 0;
    {   // Offered to two registries: kept until both are done, with no timer.
        Impl lane; registries = 2;
        check(lane.publish_seat(), "seat published");
        auto* global = live.back();
        wl_client early;
        Impl::bind_seat(&early, global->data, 9, 1);
        lane.withdraw_seat();
        check(live.size() == 1 && destroyed == 0 && lane.seat_lifetime.withdrawn() == 1,
              "a removed global stays allocated while registries may still bind it");
        check(lane.seats.front()->wl->capabilities == 0, "the withdrawn generation's seat became inert");
        wl_client racing;  // A bind sent before processing global_remove.
        Impl::bind_seat(&racing, global->data, 9, 2);
        check(racing.no_memory == 0 && lane.seats.back()->wl->capabilities == 0,
              "a bind that raced global_remove gets an inert seat, not an error");
        check(lane.publish_seat() && live.size() == 2, "the next session publishes a new generation meanwhile");
        registry_done(global);
        check(live.size() == 2 && lane.seat_lifetime.withdrawn() == 1, "one registry outstanding keeps it");
        registry_done(global);
        check(live.size() == 1 && destroyed == 1 && lane.seat_lifetime.withdrawn() == 0,
              "destroyed once every offering registry is done");
        check(lane.seat_lifetime.published(), "the current generation is untouched");
    }
    check(live.empty(), "teardown destroyed the current global");
    destroyed = 0;
    {   // libwayland < 1.26: no listener, so nothing is destroyed before teardown.
        wl_global_set_withdrawn_listener = nullptr;
        Impl lane; registries = 0;
        for (int i = 0; i < 3; ++i) {
            check(lane.publish_seat(), "seat published without a listener");
            lane.withdraw_seat();
        }
        check(live.size() == 3 && destroyed == 0 && lane.seat_lifetime.withdrawn() == 3,
              "without a listener withdrawn globals are retained");
        wl_global_set_withdrawn_listener = set_withdrawn_listener;
    }
    check(live.empty() && destroyed == 3, "teardown destroyed every retained global");
    destroyed = created = 0;
    {   // Retention is bounded: at the cap publication refuses and creates nothing.
        Impl lane; registries = 1;
        for (std::size_t i = 0; i < Lifetime::max_withdrawn; ++i) {
            check(lane.publish_seat(), "publication below the cap");
            lane.withdraw_seat();
        }
        check(lane.seat_lifetime.exhausted(), "cap reached");
        check(!lane.publish_seat() && created == static_cast<int>(Lifetime::max_withdrawn),
              "publication refused at the cap without creating a global");
        registry_done(live.front());
        check(lane.publish_seat(), "a released global makes room for the next session");
    }
    check(live.empty(), "teardown destroyed everything at the cap");
    {   // A retired lane never republishes.
        Impl lane; lane.retired = true;
        check(!lane.publish_seat() && live.empty(), "retired lane refuses publication");
    }

    registries = 0;
    {   // Per-client limit, then the lane-wide aggregate limit, for seats.
        Impl lane;
        check(lane.publish_seat(), "seat published");
        void* data = live.back()->data;
        std::vector<wl_client> clients(kMaxLaneResources / kMaxResources + 1);
        for (std::size_t i = 0; i < kMaxResources; ++i) Impl::bind_seat(&clients[0], data, 9, 1);
        check(clients[0].no_memory == 0 && lane.seats.size() == kMaxResources, "per-client bound reached");
        Impl::bind_seat(&clients[0], data, 9, 1);
        check(clients[0].no_memory == 1 && lane.seats.size() == kMaxResources, "per-client bound refuses");
        for (std::size_t c = 1; c + 1 < clients.size(); ++c)
            for (std::size_t i = 0; i < kMaxResources; ++i) Impl::bind_seat(&clients[c], data, 9, 1);
        check(lane.seats.size() == kMaxLaneResources, "lane filled by several clients within their bounds");
        auto& fresh = clients.back();
        Impl::bind_seat(&fresh, data, 9, 1);
        check(fresh.no_memory == 1 && lane.seats.size() == kMaxLaneResources,
              "the lane-wide bound refuses a client below its own bound");
        lane.seats.front()->dead = true;
        Impl::bind_seat(&fresh, data, 9, 1);
        check(fresh.no_memory == 2, "unpruned released resources still count against the lane");
        std::erase_if(lane.seats, [](auto& s) { return s->dead; });
        Impl::bind_seat(&fresh, data, 9, 1);
        check(fresh.no_memory == 2 && lane.seats.size() == kMaxLaneResources, "pruning makes room again");
    }
    {   // The same bounds for pointers, keyboards and touches.
        Impl lane;
        std::vector<wl_client> clients(kMaxLaneResources / kMaxResources + 1);
        std::vector<CWlSeat> seats;
        for (auto& client : clients) seats.emplace_back(&client, 9u, 1u);
        const auto fill = [&](auto add, auto& resources, const char* what) {
            for (auto& client : clients) client.no_memory = 0;
            for (std::size_t i = 0; i <= kMaxResources; ++i) add(&seats[0]);
            check(clients[0].no_memory == 1 && resources.size() == kMaxResources, what);
            for (std::size_t c = 1; c + 1 < seats.size(); ++c)
                for (std::size_t i = 0; i < kMaxResources; ++i) add(&seats[c]);
            check(resources.size() == kMaxLaneResources, what);
            add(&seats.back());
            check(clients.back().no_memory == 1 && resources.size() == kMaxLaneResources, what);
        };
        fill([&](CWlSeat* s) { lane.add_pointer(s, 1, 1); }, lane.pointers, "pointer bounds");
        fill([&](CWlSeat* s) { lane.add_keyboard(s, 1, 1); }, lane.keyboards, "keyboard bounds");
        fill([&](CWlSeat* s) { lane.add_touch(s, 1, 1); }, lane.touches, "touch bounds");
    }
    static_assert(kMaxLaneResources > kMaxResources && kMaxLaneResources % kMaxResources == 0);
    std::cout << "seat global lifetime tests passed\n";
}
'''


def method(source, name):
    match = re.search(r'^    \S[^\n]*\b' + name + r'\(.*?^    }', source, re.M | re.S)
    if not match:
        raise AssertionError(f'production method not found: {name}')
    return match.group()


def production_fixture(source):
    constants = re.findall(r'^constexpr std::size_t (?:kMaxResources|kMaxLaneResources) = \d+;$', source, re.M)
    if len(constants) != 2:
        raise AssertionError('production resource limits not found')
    structs = re.findall(r'^    struct (?:Seat|Pointer|Keyboard|Touch|SeatGlobal) \{[^\n]*\};$', source, re.M)
    if len(structs) != 5:
        raise AssertionError('production seat resource structs not found')
    counter = re.search(r'^    template <class Resource>\n    static std::size_t client_resources\(.*?^    }',
                        source, re.M | re.S)
    if not counter:
        raise AssertionError('production client_resources not found')
    methods = [counter.group()] + [method(source, name) for name in (
        'publish_seat', 'withdraw_seat', 'seat_withdrawn', 'bind_seat', 'add_pointer', 'add_keyboard', 'add_touch')]
    return (FIXTURE.replace('// PRODUCTION_CONSTANTS', '\n'.join(constants))
            .replace('// PRODUCTION_STRUCTS', '\n'.join(structs))
            .replace('// PRODUCTION_METHODS', '\n'.join(methods)))


class SeatGlobalLifetimeTest(unittest.TestCase):
    def test_production_withdrawal_and_resource_limits(self):
        source = (ROOT / 'src/input_experiment.cpp').read_text()
        # Fail if the tested pieces are disconnected from the production paths.
        self.assertRegex(source, r'#if WAYLAND_VERSION_MAJOR > 1 \|\| \(WAYLAND_VERSION_MAJOR == 1 && '
                                 r'WAYLAND_VERSION_MINOR >= 26\)\n#define CUA_HYPRLAND_GLOBAL_WITHDRAWN_LISTENER 1\n'
                                 r'#pragma weak wl_global_set_withdrawn_listener\n#endif')
        self.assertIn('#include <wayland-version.h>', source)
        # The admission path names the exhausted bound and never falls back.
        self.assertRegex(source, r'if \(!publish_seat\(\)\) \{\n\s+invalidate\(c\);\n(?:\s+//[^\n]*\n)?'
                                 r'\s+send\(c, seat_lifetime\.exhausted\(\) \?\n'
                                 r'\s+refusal\("agent_seat_unavailable", std::string_view\{"agent_seat_globals_exhausted"\}\) :\n'
                                 r'\s+refusal\("agent_seat_unavailable"\)\);\n\s+return;')
        # Teardown destroys every global the lane still holds.
        destructor = re.search(r'^    ~Impl\(\) \{.*?^    }', source, re.M | re.S)
        self.assertIsNotNone(destructor)
        self.assertRegex(destructor.group(), r'for \(auto\* record : seat_lifetime\.teardown\(\)\) \{\n'
                                             r'\s+wl_global_destroy\(record->global\);\n\s+delete record;')
        # Nothing else destroys a seat global: only the withdrawn listener and teardown.
        self.assertEqual(source.count('wl_global_destroy('), 2)
        compiler = shlex.split(os.environ.get('CXX', '')) or [
            shutil.which('clang++-18') or shutil.which('clang++') or 'c++']
        with tempfile.TemporaryDirectory(prefix='cua-seat-global-lifetime-') as directory:
            cpp, binary = Path(directory) / 'fixture.cpp', Path(directory) / 'fixture'
            cpp.write_text(production_fixture(source))
            build = subprocess.run([*compiler, '-std=c++20', '-Wall', '-Wextra', '-Wpedantic', '-Werror',
                                    '-I', str(ROOT / 'src'), str(cpp), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
