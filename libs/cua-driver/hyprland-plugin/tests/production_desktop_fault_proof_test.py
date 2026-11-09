"""Portable contracts only: no native VM, compositor, policy or input is touched."""
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from itertools import count
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import proofs_path  # noqa: F401  Puts ../proofs on sys.path.
import production_desktop_fault_proof as proof
from proof_fixtures import ACTIVE, BOUNDS, CANCEL, action, client, geometry_plan, inkscape_profile, trace


def plan(kind='config_disable'):
    candidate = geometry_plan()
    candidate.update(purpose='desktop_fault', fault={'kind': 'config_disable'},
        vm={'machine_id': 'a' * 32, 'boot_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'},
        compositor={'pid': 50, 'instance': 'test_1', 'uid': 1000, 'starttime': '77', 'exe': '/usr/bin/Hyprland'},
        config={'path': '/guest/input.lua', 'device': 1, 'inode': 2, 'uid': 1000,
                'mode': 0o600, 'sha256': proof.digest(proof.ENABLED.encode())})
    candidate['fault'] = {'kind': kind}
    candidate['config']['sha256'] = proof.digest(proof.fixed_bytes(kind)[0].encode())
    return candidate


def status(enabled=True):
    return {'configured': enabled, 'transport': {'ready': enabled}, 'input': {
        'protocol': 3, 'test_only': False, 'seat_lifetime': 'session', 'upgrade': 'desktop_restart',
        'transport_ready': enabled, 'lanes': [
            {'lane': lane, 'held_button': 0, 'held_keys': 0, 'drag_active': False, 'lease_active': False}
            for lane in (0, 1)]}}


def record():
    return {'result': 'observed', 'kind': 'config_disable', 'prefix': trace(ACTIVE), 'lane': 1,
            'gate_ns': 5_000_000, 'requested_ns': 6_000_000, 'acknowledged_ns': 10_000_000,
            'watchdog_deadline_ns': 90_000_000, 'before': status(), 'after': status(False),
            'config': {'sha256': proof.digest(proof.DISABLED.encode())}}


def restoration():
    return {'result': 'restored', 'started_ns': 12_000_000, 'observed_ns': 13_000_000,
            'config': {'sha256': proof.digest(proof.ENABLED.encode())}, 'status': status()}


def options(restored=True):
    values = {'kb_rules': 'evdev', 'kb_model': 'pc105', 'kb_layout': 'us',
              'kb_variant': '', 'kb_options': '' if restored else 'ctrl:nocaps', 'kb_file': ''}
    return {key: {'option': 'input:' + key, 'str': value, 'set': True} for key, value in values.items()}


def keymap_status(generation=2):
    result = status()
    for row in result['input']['lanes']:
        row.update(epoch='lane-' + str(row['lane']), desktop_generation=generation,
                   dispatches=1, reserved=False, pointer_focus=False, keyboard_focus=False)
    return result


def keymap_record():
    return {**record(), 'kind': 'keymap', 'config': {'sha256': proof.digest(proof.KEYMAP_CAPS_CTRL.encode())},
            'before': keymap_status(1), 'gate_status': keymap_status(1), 'after': keymap_status(2),
            'keymap_before': options(), 'keymap_after': options(False)}


def keymap_restoration():
    return {**restoration(), 'config': {'sha256': proof.digest(proof.KEYMAP_US.encode())},
            'keymap_options': options(), 'status': keymap_status(3)}


def motion_trace(distance=12):
    page = trace(ACTIVE[:2] + [(2, 'pointer_enter', 1, 0)] + ACTIVE[2:])
    page['events'][2].extend([20, 30])
    page['events'][-1].extend([20 + distance, 30])
    return page


def target_snapshot(identity, *, runtime=100, observed_ns=1_000_000):
    return {'pid': 20, 'window_id': 200, 'window_bounds': dict(BOUNDS), 'snapshot_id': identity,
            'proof_runtime': {'pid': runtime, 'directory': f'/synthetic/runtime-{runtime}'},
            'proof_observation_started_ns': observed_ns, 'proof_observation_finished_ns': observed_ns + 100_000}


RETIRED = 'retained_inert retired: session-lifetime agent seats withdraw on desktop transitions'


def cleared_evidence(kind='keymap'):
    """Saved evidence of a cancelled drag whose transition cleared every lane."""
    candidate = keymap_record() if kind == 'keymap' else record()
    restored = keymap_restoration() if kind == 'keymap' else restoration()
    candidate.update(pointer_cleanup='cleared', prefix=motion_trace())
    boundary = deepcopy(candidate['prefix'])
    boundary['events'] += [[7, 8_000_000, 'agent_cancel', 100, 100, 1, 0],
                           [8, 9_000_000, 'pointer_button', 100, 100, 1, 0],
                           [9, 9_500_000, 'pointer_leave', 100, 100, 1, 0]]
    boundary['count'] = len(boundary['events'])
    return boundary, candidate, restored


class PointerCleanupPolicyTests(unittest.TestCase):
    """Session-lifetime seats (#4257) leave only the 'cleared' policy certifiable."""

    def test_plan_accepts_only_cleared_and_names_the_retired_policy(self):
        for kind in ('config_disable', 'keymap'):
            proof.validate_plan(plan(kind))
            for policy in ('cleared', 'retained_inert', None, True, 'retained', {}, []):
                candidate = plan(kind)
                candidate['fault']['pointer_cleanup'] = policy
                with self.subTest(kind=kind, policy=policy):
                    if policy == 'cleared':
                        proof.validate_plan(candidate)
                    elif policy == 'retained_inert':
                        with self.assertRaisesRegex(AssertionError, RETIRED):
                            proof.validate_plan(candidate)
                    else:
                        with self.assertRaisesRegex(AssertionError, 'unknown pointer cleanup policy'):
                            proof.validate_plan(candidate)

    def test_saved_retained_evidence_is_rejected_at_every_policy_entry_point(self):
        for kind in ('config_disable', 'keymap'):
            boundary, candidate, restored = cleared_evidence(kind)
            result = proof.verify_fault(boundary, candidate, restored, action())
            self.assertEqual(result['result'], 'verified')
            self.assertNotIn('pointer_cleanup', result)
            candidate['pointer_cleanup'] = 'retained_inert'
            with self.subTest(kind=kind), self.assertRaisesRegex(AssertionError, RETIRED):
                proof.verify_fault(boundary, candidate, restored, action())
            with self.subTest(kind=kind), self.assertRaisesRegex(AssertionError, RETIRED):
                proof.verify_cancelled(boundary, candidate, restored['started_ns'])
        with self.assertRaisesRegex(AssertionError, RETIRED):
            proof.verify_keymap_transition(keymap_status(1), keymap_status(2), 'retained_inert')

    def test_live_keymap_injection_requires_cleared_pointer_after_transition(self):
        cases = [('keymap', failure) for failure in (None, 'gate_released', 'after_focus', 'after_held')]
        cases += [('config_disable', None)]
        for kind, failure in cases:
            with self.subTest(kind=kind, failure=failure), ExitStack() as stack:
                _, candidate, _ = cleared_evidence(kind)
                gate = keymap_status(1)
                gate['input']['lanes'][0].update(held_button=272, drag_active=True, lease_active=True,
                                                 pointer_focus=True, reserved=True)
                after = candidate['after']
                fault = object.__new__(proof.ConfigFault)
                fault.config = {'kind': kind, 'pointer_cleanup': 'cleared', 'instance': 'exact',
                                'path': '/unused', 'deadline_ns': 10_000_000_000}
                fault.child = Mock(poll=Mock(return_value=None))
                fault.record = {'kind': kind, 'pointer_cleanup': 'cleared', 'before': keymap_status(1)}
                fault.mutated = False
                if failure == 'gate_released':
                    gate['input']['lanes'][0]['held_button'] = 0
                if failure == 'after_focus':
                    after['input']['lanes'][0]['pointer_focus'] = True
                if failure == 'after_held':
                    after['input']['lanes'][0]['held_button'] = 272
                status = stack.enter_context(patch.object(proof, 'production_status', return_value=gate))
                stack.enter_context(patch.object(proof, 'keymap_options', side_effect=[options(), options(False)]))
                stack.enter_context(patch.object(proof, '_locked', side_effect=lambda _: nullcontext()))
                stack.enter_context(patch.object(proof, 'poll_fault_active', return_value=(candidate['prefix'], {1: 2})))
                stack.enter_context(patch.object(proof.time, 'monotonic_ns', side_effect=[5_000_000, 6_000_000, 10_000_000]))
                atomic = stack.enter_context(patch.object(proof, '_replace', side_effect=lambda *_args, **kwargs: kwargs['before_replace']()))
                stack.enter_context(patch.object(proof, '_reload', return_value=after))
                stack.enter_context(patch.object(proof, 'file_identity', return_value=candidate['config']))
                if failure:
                    with self.assertRaises(AssertionError):
                        fault.inject(Mock(), trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), Mock())
                else:
                    fault.inject(Mock(), trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), Mock())
                    self.assertEqual(fault.config['lane'], 1)
                    self.assertTrue(all(row['pointer_focus'] is False
                                        for row in fault.record['after']['input']['lanes'] if 'pointer_focus' in row))
                # Only the keymap fault reads a live status gate before mutation.
                self.assertEqual(status.call_count, int(kind == 'keymap'))
                self.assertEqual(atomic.call_count, int(failure != 'gate_released'))

    def test_cleared_cleanup_status_requires_no_pointer_focus_or_authority(self):
        fields = [('held_button', 272), ('held_button', False), ('held_keys', 1), ('held_keys', True),
                  ('drag_active', True), ('lease_active', True), ('keyboard_focus', True),
                  ('reserved', True), ('pointer_focus', True), ('pointer_focus', 1), ('pointer_focus', None)]
        for stage in ('after', 'restored'):
            for lane in (0, 1):
                for key, value in fields:
                    boundary, candidate, restored = cleared_evidence('keymap')
                    observed = restored['status'] if stage == 'restored' else candidate[stage]
                    observed['input']['lanes'][lane][key] = value
                    with self.subTest(stage=stage, lane=lane, key=key, value=value), self.assertRaises(AssertionError):
                        proof.verify_fault(boundary, candidate, restored, action())

    def test_cleared_trace_cannot_hide_retarget_motion_new_input_or_missing_release(self):
        for kind in ('config_disable', 'keymap'):
            for event in ('pointer_enter', 'pointer_motion', 'keyboard_key', 'pointer_axis',
                          'agent_admitted', 'agent_drag_end', 'agent_action_end'):
                boundary, candidate, restored = cleared_evidence(kind)
                boundary['events'].append([10, 11_000_000, event, 100, 100, 1, 0] +
                                          ([32, 30] if event in ('pointer_enter', 'pointer_motion') else []))
                boundary['count'] += 1
                with self.subTest(kind=kind, event=event), self.assertRaises(AssertionError):
                    proof.verify_fault(boundary, candidate, restored, action())
            for missing in ('release', 'cancel', 'coordinates'):
                boundary, candidate, restored = cleared_evidence(kind)
                if missing == 'coordinates':
                    candidate['min_motion_px'] = 12
                    del candidate['prefix']['events'][-1][7:9]
                    del boundary['events'][5][7:9]
                else:
                    boundary['events'].pop(-2 if missing == 'release' else -3)
                    boundary['count'] -= 1
                with self.subTest(kind=kind, missing=missing), self.assertRaises(AssertionError):
                    proof.verify_fault(boundary, candidate, restored, action())

    def test_epoch_generation_policy_and_lane_cannot_be_substituted(self):
        for change in ('epoch', 'generation', 'policy', 'lane'):
            boundary, candidate, restored = cleared_evidence()
            if change in ('epoch', 'generation'):
                candidate['after']['input']['lanes'][0][
                    'epoch' if change == 'epoch' else 'desktop_generation'] = 'replacement' if change == 'epoch' else 1
            else:
                candidate[{'policy': 'pointer_cleanup', 'lane': 'lane'}[change]] = {
                    'policy': 'retained_inert', 'lane': 2}[change]
            with self.subTest(change=change), self.assertRaises(AssertionError):
                proof.verify_fault(boundary, candidate, restored, action())


class MotionGateTests(unittest.TestCase):
    def test_plan_optional_positive_finite_threshold_for_both_faults(self):
        for kind in ('config_disable', 'keymap'):
            proof.validate_plan(plan(kind))
            for value in (12, 12.5, 0, -1, True, None, '12', float('nan'), float('inf')):
                candidate = plan(kind)
                candidate['fault']['min_motion_px'] = value
                with self.subTest(kind=kind, value=value):
                    if type(value) in (int, float) and value in (12, 12.5):
                        proof.validate_plan(candidate)
                    else:
                        with self.assertRaises(AssertionError):
                            proof.validate_plan(candidate)

    def test_omitted_threshold_preserves_held_only_gate(self):
        page = trace(ACTIVE[:4])
        transport = Mock(collect=Mock(return_value=page))
        self.assertEqual(proof.poll_fault_active(transport, trace(ACTIVE[:1]),
                         Mock(done=Mock(return_value=False))), (page, {1: 2_000_000}))

    def test_exact_threshold_waits_for_same_lane_surface_motion(self):
        first = motion_trace(11.999)
        enough = deepcopy(first)
        enough['events'].append([7, 4_500_000, 'pointer_motion', 100, 100, 1, 0, 32, 30])
        enough['count'] += 1
        transport = Mock(collect=Mock(side_effect=[first, enough]))
        pending = Mock(done=Mock(return_value=False))
        with patch.object(proof.time, 'sleep') as sleep:
            self.assertEqual(proof.poll_fault_active(transport, trace(ACTIVE[:1]), pending, 12),
                             (enough, {1: 2_000_000}))
        self.assertEqual(transport.collect.call_count, 2)
        self.assertEqual(pending.done.call_count, 2)
        sleep.assert_not_called()
        diagonal = motion_trace()
        diagonal['events'][-1][7:9] = [23, 34]
        self.assertEqual(proof.drag_motion_px(diagonal, 1), 5)

    def test_missing_or_insufficient_post_press_motion_expires_without_replay(self):
        for page in (motion_trace(11.999), {**motion_trace(), 'events': motion_trace()['events'][:-1], 'count': 5}):
            with self.subTest(page=page), patch.object(proof.time, 'monotonic', side_effect=lambda: next(ticks) / 1000):
                ticks = count()
                transport = Mock(collect=Mock(return_value=page))
                with self.assertRaisesRegex(AssertionError, 'bounded wait'):
                    proof.poll_fault_active(transport, trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), 12, timeout=.02)
                self.assertGreater(transport.collect.call_count, 1)

    def test_rejects_missing_coordinates_wrong_lane_changed_identity_and_ended_drag(self):
        for failure in ('coordinates', 'initial', 'foreign_lane', 'wrong_lane', 'leave', 'enter', 'release', 'cancel'):
            page = motion_trace()
            if failure == 'coordinates':
                del page['events'][-1][7:9]
            elif failure == 'initial':
                page['events'][2] = [3, 2_000_000, 'cursor', 100, 100, 0, 0]
            elif failure == 'foreign_lane':
                page['events'][-1][5] = 2
            elif failure not in ('wrong_lane',):
                kind, value = {'leave': ('pointer_leave', 0), 'enter': ('pointer_enter', 0),
                               'release': ('pointer_button', 0), 'cancel': ('agent_cancel', 0)}[failure]
                page['events'].append([7, 4_500_000, kind, 100, 100, 1, value] + ([32, 30] if failure == 'enter' else []))
                page['count'] += 1
            with self.subTest(failure=failure), self.assertRaises(AssertionError):
                proof.drag_motion_px(page, 2 if failure == 'wrong_lane' else 1)

    def test_poll_rejects_changed_trace_history_incomplete_and_stale_reads(self):
        first = motion_trace(1)
        changed = motion_trace(12)
        with self.assertRaisesRegex(AssertionError, 'history'):
            proof.poll_fault_active(Mock(collect=Mock(side_effect=[first, changed])), trace(ACTIVE[:1]),
                                    Mock(done=Mock(return_value=False)), 12)
        # Page validity is owned by trace_interval (realapp TraceIntervalTests); one case proves wiring.
        with self.assertRaisesRegex(AssertionError, 'dropped events'):
            proof.poll_fault_active(Mock(collect=Mock(return_value={**motion_trace(), 'overflow': True})),
                                    trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), 12)
        with patch.object(proof.time, 'monotonic', side_effect=[0, .01, .02, .03, .04, .30]), \
             self.assertRaisesRegex(AssertionError, 'stale'):
            proof.poll_fault_active(Mock(collect=Mock(return_value=motion_trace())), trace(ACTIVE[:1]),
                                    Mock(done=Mock(return_value=False)), 12)

    def test_saved_fault_gate_rechecks_threshold_from_trace(self):
        candidate = {**record(), 'prefix': motion_trace(), 'min_motion_px': 12}
        boundary = motion_trace()
        boundary['events'] += [[i + 7, ms * 1_000_000, kind, 100, 100, lane, value]
                               for i, (ms, kind, lane, value) in enumerate(CANCEL[len(ACTIVE):])]
        boundary['count'] = len(boundary['events'])
        proof.verify_fault(boundary, candidate, restoration(), action())
        for threshold in (12.001, True, float('nan')):
            with self.subTest(threshold=threshold), self.assertRaises(AssertionError):
                proof.verify_fault(boundary, {**candidate, 'min_motion_px': threshold}, restoration(), action())


class KeymapTests(unittest.TestCase):
    def test_fault_fixture_keeps_us_layout_and_changes_only_options(self):
        self.assertIn('kb_options = ""', proof.KEYMAP_US)
        self.assertEqual(proof.KEYMAP_CAPS_CTRL,
                         proof.KEYMAP_US.replace('kb_options = ""', 'kb_options = "ctrl:nocaps"'))
        self.assertEqual(proof.fixed_bytes('keymap'), (proof.KEYMAP_US, proof.KEYMAP_CAPS_CTRL))

    def test_idle_baseline_allows_only_unreserved_inert_hover_on_either_lane(self):
        for lane in (0, 1):
            passive = keymap_status(1)
            passive['input']['lanes'][lane]['pointer_focus'] = True
            proof.idle_lanes(passive)
            proof.verify_keymap_transition(passive, keymap_status(2))
            with self.assertRaises(AssertionError):
                proof.keymap_lanes(passive, cleared=True)
            for key, value in (('held_button', 272), ('held_button', False), ('held_keys', 1),
                               ('drag_active', True), ('lease_active', True), ('keyboard_focus', True),
                               ('reserved', True), ('reserved', None), ('pointer_focus', 1),
                               ('pointer_focus', None)):
                changed = deepcopy(passive)
                changed['input']['lanes'][lane][key] = value
                with self.subTest(lane=lane, key=key, value=value), self.assertRaises(AssertionError):
                    proof.idle_lanes(changed)

    def test_keymap_constructor_preserves_and_checks_passive_baseline_before_staging(self):
        for reserved in (False, True):
            with self.subTest(reserved=reserved), tempfile.TemporaryDirectory() as root, ExitStack() as stack:
                directory = Path(root).resolve()
                path = directory / 'keymap.lua'
                path.write_text(proof.KEYMAP_US)
                path.chmod(0o600)
                candidate = plan('keymap')
                candidate['config'] = {'path': str(path), **proof.file_identity(path)}
                candidate['compositor']['uid'] = os.getuid()
                identity = {k: v for k, v in candidate['compositor'].items() if k != 'instance'}
                before = keymap_status(1)
                before['input']['lanes'][0].update(pointer_focus=True, reserved=reserved)
                stack.enter_context(patch.object(proof.platform, 'system', return_value='Linux'))
                stack.enter_context(patch.object(proof.subprocess, 'run', return_value=Mock(returncode=0)))
                stack.enter_context(patch.object(proof, '_identity', return_value=identity))
                stack.enter_context(patch.object(proof, '_guard'))
                stack.enter_context(patch.object(proof, 'production_status', return_value=before))
                stack.enter_context(patch.object(proof, 'keymap_options', return_value=options()))
                if reserved:
                    with patch.object(proof.tempfile, 'mkstemp') as stage, self.assertRaisesRegex(AssertionError, 'authority'):
                        proof.ConfigFault(candidate, directory)
                    stage.assert_not_called()
                else:
                    fault = proof.ConfigFault(candidate, directory)
                    fault.close()
                self.assertEqual(json.loads((directory / 'pre-fault-status.json').read_text()), before)
                self.assertEqual(path.read_text(), proof.KEYMAP_US)

    def test_keymap_plan_requires_its_own_exact_include(self):
        proof.validate_plan(plan('keymap'))
        for kind, data in (('keymap', proof.ENABLED), ('config_disable', proof.KEYMAP_US),
                           ('keymap', proof.KEYMAP_CAPS_CTRL), ('keymap', proof.KEYMAP_US + '-- extra\n')):
            candidate = plan(kind)
            candidate['config']['sha256'] = proof.digest(data.encode())
            with self.subTest(kind=kind, data=data), self.assertRaises(AssertionError):
                proof.validate_plan(candidate)

    def test_compiled_map_gate_and_original_map_restoration_pass(self):
        result = proof.verify_fault(trace(CANCEL), keymap_record(), keymap_restoration(), action())
        self.assertEqual(result['result'], 'verified')
        self.assertNotIn('legacy_wrong_layout', result)

    def test_exact_option_readback_rejects_labels_variants_options_and_override(self):
        for key in options():
            candidate = options()
            candidate[key]['str'] = 'wrong'
            with self.subTest(key=key), self.assertRaises(AssertionError):
                proof.verify_keymap_options(candidate, True)
        for candidate in ({}, {'active_keymap': 'English (US)'}, {**options(), 'other': {}}):
            with self.assertRaises(AssertionError):
                proof.verify_keymap_options(candidate, True)
        with patch.object(proof, '_hypr', side_effect=lambda _, *_args: json.dumps(options(False)[_args[-1].split(':')[1]])) as hypr:
            self.assertEqual(proof.keymap_options('exact', False), options(False))
            self.assertEqual(hypr.call_count, 6)

    def test_transition_requires_real_generation_same_epoch_and_retired_authority(self):
        for key, value in (('desktop_generation', 1), ('desktop_generation', True), ('epoch', 'replaced'),
                           ('reserved', True), ('held_button', 272), ('held_button', False), ('held_keys', 1),
                           ('drag_active', True), ('lease_active', True), ('pointer_focus', True), ('keyboard_focus', True)):
            after = keymap_status(2)
            after['input']['lanes'][0][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                proof.verify_keymap_transition(keymap_status(1), after)

    def test_restoration_requires_original_options_and_new_generation(self):
        for mutate, message in ((lambda r: r.update(keymap_options=options(False)), 'keymap option'),
                                (lambda r: r.update(config={'sha256': proof.digest(proof.ENABLED.encode())}), ''),
                                # These reach the live after-to-restoration keymap transition.
                                (lambda r: r.update(status=keymap_status(2)), 'did not invalidate authority'),
                                (lambda r: r['status']['input']['lanes'][1].update(epoch='replaced'), 'lane replaced'),
                                (lambda r: r['status']['input']['lanes'][0].update(reserved=True),
                                 'reservation survived')):
            restored = keymap_restoration()
            mutate(restored)
            with self.subTest(message=message), self.assertRaisesRegex(AssertionError, message):
                proof.verify_fault(trace(CANCEL), keymap_record(), restored, action())
        for mutate in (lambda r: r.update(after=keymap_status(1)),
                       lambda r: r.update(keymap_after=options())):
            candidate = keymap_record()
            mutate(candidate)
            with self.assertRaises(AssertionError):
                proof.verify_fault(trace(CANCEL), candidate, keymap_restoration(), action())

class OracleTests(unittest.TestCase):
    def test_partial_unknown_and_exact_history_pass_without_claiming_app_effect(self):
        for observed in (action(), {'outcome': 'unknown', 'replayed': False}):
            result = proof.verify_fault(trace(CANCEL), record(), restoration(), observed)
            self.assertEqual(result['result'], 'verified')
            self.assertEqual(result['saved_document_effect'], 'unproven')

    def test_missing_press_release_or_cancel_cross_lane_and_replay_fail(self):
        cases = [ACTIVE, CANCEL[:6] + CANCEL[7:], CANCEL[:5] + CANCEL[6:]]
        for kind in ('agent_admitted', 'agent_drag_end', 'agent_action_end', 'keyboard_key',
                     'pointer_axis', 'pointer_enter', 'pointer_motion'):
            cases.append(CANCEL + [(11, kind, 1, 0)])
        cases.append(CANCEL + [(11, 'pointer_leave', 2, 0)])
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(AssertionError):
                proof.verify_fault(trace(rows), record(), restoration(), action())
        candidate = record()
        candidate['prefix'] = trace(ACTIVE[:3])
        with self.assertRaises(AssertionError):
            proof.verify_fault(trace(CANCEL), candidate, restoration(), action())
        with self.assertRaises(AssertionError):
            proof.verify_fault(trace(CANCEL), record(), restoration(), {**action(), 'replayed': True})

    def test_fault_cancellation_and_release_must_precede_restoration(self):
        for changes in ({'requested_ns': 9_000_000}, {'gate_ns': 7_000_000},
                        {'watchdog_deadline_ns': 12_000_000}):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                proof.verify_fault(trace(CANCEL), {**record(), **changes}, restoration(), action())
        # Isolate the 250 ms gate-to-request bound; every ordering check still holds.
        for requested_ms, stale in ((255, False), (256, True)):
            late_cancel = ACTIVE + [(requested_ms, 'agent_cancel', 1, 0), (requested_ms + 1, 'pointer_button', 1, 0),
                                    (requested_ms + 1, 'pointer_leave', 1, 0)]
            candidate = {**record(), 'gate_ns': 5_000_000, 'requested_ns': requested_ms * 1_000_000,
                         'acknowledged_ns': (requested_ms + 1) * 1_000_000, 'watchdog_deadline_ns': 1_000_000_000}
            restored = {**restoration(), 'started_ns': (requested_ms + 2) * 1_000_000,
                        'observed_ns': (requested_ms + 3) * 1_000_000}
            with self.subTest(requested_ms=requested_ms):
                if stale:
                    with self.assertRaisesRegex(AssertionError, 'stale fault gate'):
                        proof.verify_fault(trace(late_cancel), candidate, restored, action())
                else:
                    self.assertEqual(proof.verify_fault(trace(late_cancel), candidate, restored, action())['result'],
                                     'verified')
        late = ACTIVE + [(12, 'agent_cancel', 1, 0), (13, 'pointer_button', 1, 0)]
        with self.assertRaisesRegex(AssertionError, 'during fault'):
            proof.verify_fault(trace(late), record(), restoration(), action())
        late_release = ACTIVE + [(8, 'agent_cancel', 1, 0), (12, 'pointer_button', 1, 0)]
        with self.assertRaisesRegex(AssertionError, 'delayed'):
            proof.verify_fault(trace(late_release), record(), restoration(), action())

    def test_reconnected_trace_must_be_complete_and_preserve_prefix(self):
        # Page validity is owned by trace_interval (realapp TraceIntervalTests); one case proves wiring.
        with self.assertRaisesRegex(AssertionError, 'dropped events'):
            proof.verify_fault({**trace(CANCEL), 'overflow': True}, record(), restoration(), action())
        for page in (trace(CANCEL[5:]), trace(CANCEL)):
            page['events'][1][1] += 1
            with self.assertRaises(AssertionError):
                proof.verify_fault(page, record(), restoration(), action())

    def test_primary_input_fails_the_fault(self):
        # Primary classification is owned by primary_trace_test; one case proves wiring.
        with self.assertRaisesRegex(AssertionError, "'result': 'failed'"):
            proof.verify_fault(trace(CANCEL + [(11, 'keyboard_key', 0, 1)]), record(), restoration(), action())

    def test_exact_fault_bytes_and_restoration_required(self):
        for key, value in (('result', 'unproven'), ('kind', 'keymap'), ('config', {'sha256': 'bad'})):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                proof.verify_fault(trace(CANCEL), {**record(), key: value}, restoration(), action())
        for update in ({'result': 'not_needed'}, {'config': {'sha256': 'bad'}}, {'status': status(False)}):
            with self.assertRaises(AssertionError):
                proof.verify_fault(trace(CANCEL), record(), {**restoration(), **update}, action())


class SafetyTests(unittest.TestCase):
    def test_inkscape_only_profile_reaches_the_shared_app_profile_gate(self):
        candidate = inkscape_profile(plan())
        proof.validate_plan(candidate)
        candidate['agents'][0]['document'] = '/synthetic/private.svg'
        with self.assertRaisesRegex(AssertionError, 'absolute synthetic SVG document'):
            proof.validate_plan(candidate)

    def test_plan_rejects_other_faults_and_incomplete_identity(self):
        proof.validate_plan(plan())
        for change in ({'disposable': False}, {'fault': {'kind': 'keymap'}}, {'fault': {'kind': 'dpms'}},
                       {'fault': {'kind': 'lock'}}, {'vm': {'machine_id': 'bad', 'boot_id': 'bad'}},
                       {'config': {**plan()['config'], 'sha256': 'arbitrary config'}},
                       {'compositor': {**plan()['compositor'], 'exe': '/usr/bin/other'}},
                       {'recovery': {'pointer_stage': 'select_range'}}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                proof.validate_plan({**plan(), **change})

    def test_host_bare_metal_and_wrong_process_refused_before_file_access(self):
        for system, vm_return in (('Darwin', 0), ('Linux', 1)):
            with patch.object(proof.platform, 'system', return_value=system), \
                 patch.object(proof.subprocess, 'run', return_value=Mock(returncode=vm_return)), \
                 patch.object(proof, 'file_identity') as files, self.assertRaises(AssertionError):
                proof.ConfigFault(plan(), Path('/unused'))
            files.assert_not_called()
        with patch.object(proof.platform, 'system', return_value='Linux'), \
             patch.object(proof.subprocess, 'run', return_value=Mock(returncode=0)), \
             patch.object(proof.os, 'getuid', return_value=1000), \
             patch.object(proof, '_identity', return_value={}), \
             patch.object(proof, 'file_identity') as files, self.assertRaises(AssertionError):
            proof.ConfigFault(plan(), Path('/unused'))
        files.assert_not_called()

    def test_status_rejects_old_signed_and_uncleared_native_state(self):
        for enabled in (True, False):
            with patch.object(proof, '_hypr', return_value=json.dumps(status(enabled))):
                proof.production_status('exact', enabled)
        # 'compositor' is the old always-advertised contract (#4257), now refused.
        mutations = [('protocol', 0), ('test_only', True), ('seat_lifetime', 'action'),
                     ('seat_lifetime', 'compositor'), ('transport_ready', True)]
        for key, value in mutations:
            candidate = status(False)
            candidate['input'][key] = value
            with patch.object(proof, '_hypr', return_value=json.dumps(candidate)), self.assertRaises(AssertionError):
                proof.production_status('exact', False)
        for key, value in (('held_button', True), ('held_keys', 1), ('drag_active', True), ('lease_active', True)):
            candidate = status(False)
            candidate['input']['lanes'][1][key] = value
            with patch.object(proof, '_hypr', return_value=json.dumps(candidate)), self.assertRaises(AssertionError):
                proof.production_status('exact', False)
        candidate = status(False)
        candidate['experiment'] = candidate.pop('input')
        with patch.object(proof, '_hypr', return_value=json.dumps(candidate)), self.assertRaises(AssertionError):
            proof.production_status('exact', False)

    def prepare_files(self, directory, kind='config_disable'):
        config = {'kind': kind, 'path': str(directory / 'input.lua'), 'files': {}}
        original, changed = proof.fixed_bytes(kind)
        for name, data in (('original', original), ('disabled', changed), ('restored', original)):
            path = Path(config['path']) if name == 'original' else directory / (name + '.stage')
            path.write_bytes(data.encode())
            path.chmod(0o600)
            config['files'][name] = {'path': str(path), 'identity': proof.file_identity(path)}
        return config

    def test_atomic_fixed_transition_restores_exact_bytes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root, patch.object(proof, '_guard'):
            config = self.prepare_files(Path(root).resolve())
            proof._replace(config, False)
            self.assertEqual(Path(config['path']).read_bytes(), proof.DISABLED.encode())
            self.assertEqual(proof.file_identity(config['path']), config['files']['disabled']['identity'])
            proof._replace(config, True)
            proof._replace(config, True)
            self.assertEqual(Path(config['path']).read_bytes(), proof.ENABLED.encode())
            self.assertEqual(proof.file_identity(config['path']), config['files']['restored']['identity'])

    def test_keymap_atomic_replacement_restoration_and_guarded_failures(self):
        for failure in (None, 'unrelated', 'wrong_stage', 'reload'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root, ExitStack() as stack:
                config = self.prepare_files(Path(root).resolve(), 'keymap')
                config['instance'] = 'exact'
                stack.enter_context(patch.object(proof, '_guard'))
                stack.enter_context(patch.object(proof, '_locked', side_effect=lambda _: nullcontext()))
                stack.enter_context(patch.object(proof, '_reload', side_effect=TimeoutError('lost') if failure == 'reload' else lambda *_: keymap_status(3)))
                readback = stack.enter_context(patch.object(proof, 'keymap_options', return_value=options()))
                proof._replace(config, False)
                self.assertEqual(Path(config['path']).read_bytes(), proof.KEYMAP_CAPS_CTRL.encode())
                if failure == 'unrelated':
                    Path(config['path']).write_bytes(proof.DISABLED.encode())
                if failure == 'wrong_stage':
                    Path(config['files']['restored']['path']).write_bytes(proof.ENABLED.encode())
                if failure:
                    with self.assertRaises((AssertionError, TimeoutError)):
                        proof.restore_config(config)
                    readback.assert_not_called()
                else:
                    restored = proof.restore_config(config)
                    self.assertEqual(restored['keymap_options'], options())
                    self.assertEqual(Path(config['path']).read_bytes(), proof.KEYMAP_US.encode())
                    proof._replace(config, True)

    def test_unrelated_bytes_inode_symlink_and_stage_change_preserved(self):
        for change in ('bytes', 'inode', 'link', 'stage'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root, patch.object(proof, '_guard'):
                config = self.prepare_files(Path(root).resolve())
                proof._replace(config, False)
                path = Path(config['path'])
                if change == 'bytes':
                    path.write_bytes(b'unrelated')
                elif change == 'inode':
                    replacement = path.with_name('replacement')
                    replacement.write_bytes(proof.DISABLED.encode())
                    replacement.chmod(0o600)
                    os.replace(replacement, path)
                elif change == 'link':
                    path.unlink()
                    path.symlink_to(config['files']['restored']['path'])
                else:
                    Path(config['files']['restored']['path']).write_bytes(b'unrelated')
                with patch.object(proof.os, 'replace') as replace, self.assertRaises(AssertionError):
                    proof._replace(config, True)
                replace.assert_not_called()

    def test_group_writable_and_hardlinked_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root).resolve() / 'input.lua'
            path.write_bytes(proof.ENABLED.encode())
            path.chmod(0o666)
            with self.assertRaises(AssertionError):
                proof.file_identity(path)
            path.chmod(0o600)
            os.link(path, path.with_name('alias'))
            with self.assertRaises(AssertionError):
                proof.file_identity(path)

    def test_constructor_stages_only_fixed_bytes_and_close_preserves_original(self):
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            directory = Path(root).resolve()
            path = directory / 'input.lua'
            path.write_bytes(proof.ENABLED.encode())
            path.chmod(0o600)
            candidate = plan()
            candidate['fault']['min_motion_px'] = 12
            candidate['fault']['pointer_cleanup'] = 'retained_inert'
            candidate['config'] = {'path': str(path), **proof.file_identity(path)}
            retired = deepcopy(candidate)
            candidate['fault']['pointer_cleanup'] = 'cleared'
            candidate['compositor']['uid'] = os.getuid()
            identity = {k: v for k, v in candidate['compositor'].items() if k != 'instance'}
            stack.enter_context(patch.object(proof.platform, 'system', return_value='Linux'))
            stack.enter_context(patch.object(proof.subprocess, 'run', return_value=Mock(returncode=0)))
            stack.enter_context(patch.object(proof, '_identity', return_value=identity))
            stack.enter_context(patch.object(proof, '_guard'))
            stack.enter_context(patch.object(proof, 'production_status', return_value=keymap_status(1)))
            reload = stack.enter_context(patch.object(proof, '_reload'))
            # The retired policy refuses before any status read or staged file.
            with self.assertRaisesRegex(AssertionError, 'retained_inert retired'):
                proof.ConfigFault(retired, directory)
            self.assertEqual(set(directory.iterdir()), {path})
            fault = proof.ConfigFault(candidate, directory)
            self.assertEqual(fault.config['min_motion_px'], 12)
            self.assertEqual(fault.record['min_motion_px'], 12)
            self.assertEqual(fault.config['pointer_cleanup'], 'cleared')
            self.assertEqual(fault.record['pointer_cleanup'], 'cleared')
            self.assertNotIn('target', fault.record)
            original = proof.file_identity(path)
            for name, data in (('disabled', proof.DISABLED), ('restored', proof.ENABLED)):
                staged = Path(fault.config['files'][name]['path'])
                self.assertEqual(staged.read_bytes(), data.encode())
                self.assertEqual(staged.suffix, '.stage')
            fault.close()
            self.assertEqual(proof.file_identity(path), original)
            self.assertEqual(set(directory.iterdir()), {path, directory / 'pre-fault-status.json'})
            reload.assert_not_called()

    def test_final_active_gate_failure_prevents_atomic_replacement(self):
        with tempfile.TemporaryDirectory() as root, patch.object(proof, '_guard'):
            config = self.prepare_files(Path(root).resolve())
            with patch.object(proof.os, 'replace') as replace, self.assertRaisesRegex(AssertionError, 'stale'):
                proof._replace(config, False, before_replace=Mock(side_effect=AssertionError('stale')))
            replace.assert_not_called()
            self.assertEqual(Path(config['path']).read_bytes(), proof.ENABLED.encode())

    def test_restore_readback_failure_preserves_cleanup_obligation(self):
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            config = self.prepare_files(Path(root).resolve())
            stack.enter_context(patch.object(proof, '_guard'))
            stack.enter_context(patch.object(proof, '_locked', side_effect=lambda _: nullcontext()))
            stack.enter_context(patch.object(proof, '_reload', side_effect=TimeoutError('lost reload reply')))
            proof._replace(config, False)
            with self.assertRaises(TimeoutError):
                proof.restore_config(config)
            self.assertEqual(Path(config['path']).read_bytes(), proof.ENABLED.encode())
            # Restored bytes alone are not acknowledgment; retry must reload.
            with self.assertRaises(TimeoutError):
                proof.restore_config(config)

    def test_stale_vm_prevents_compositor_commands(self):
        with patch.object(proof.platform, 'system', return_value='Linux'), \
             patch.object(proof, 'guest_identity', return_value={}), \
             patch.object(proof, '_same_compositor') as compositor, self.assertRaises(AssertionError):
            proof._guard({'vm': plan()['vm']})
        compositor.assert_not_called()

    def test_trace_reconnection_binds_exact_compositor_peer_and_protocol(self):
        for peer, protocol in (((50, 1000, 1000), 3), ((51, 1000, 1000), 3),
                               ((50, 1001, 1000), 3), ((50, 1000, 1000), 0)):
            connection = Mock(hello={'protocol': protocol})
            connection.socket.getsockopt.return_value = struct.pack('3i', *peer)
            with patch.object(proof, '_guard') as guard, patch.object(proof.socket, 'SO_PEERCRED', 17, create=True):
                if peer[:2] == (50, 1000) and protocol == 3:
                    proof.verify_trace_peer(connection, {'compositor': plan()['compositor']})
                    guard.assert_called_once()
                else:
                    with self.assertRaises(AssertionError):
                        proof.verify_trace_peer(connection, {'compositor': plan()['compositor']})
                    guard.assert_not_called()

    def controller(self):
        fault = object.__new__(proof.ConfigFault)
        fault.config = {'path': '/unused', 'deadline_ns': 10_000_000_000}
        fault.child = Mock(poll=Mock(return_value=None))
        fault.cancel_fd = 8
        fault.record = {'result': 'unproven', 'kind': 'config_disable'}
        fault.restoration = None
        fault.mutated = False
        return fault

    def test_watchdog_has_fixed_bounded_budget_for_each_fault(self):
        for kind, seconds in (('config_disable', 12), ('keymap', 30)):
            with self.subTest(kind=kind), ExitStack() as stack:
                fault = self.controller()
                fault.config['kind'] = kind
                fault.child = None
                child = Mock()
                child.stdout.readline.return_value = 'ARMED\n'
                stack.enter_context(patch.object(proof.time, 'monotonic_ns', return_value=100))
                stack.enter_context(patch.object(proof.os, 'pipe', return_value=(7, 8)))
                close = stack.enter_context(patch.object(proof.os, 'close'))
                launch = stack.enter_context(patch.object(proof.subprocess, 'Popen', return_value=child))
                stack.enter_context(patch.object(proof.select, 'select', return_value=([child.stdout], [], [])))
                fault.arm()
                self.assertEqual(fault.config['deadline_ns'], 100 + seconds * 1_000_000_000)
                self.assertLess(seconds * 1000, proof.PRIMARY_LIFETIME_MS)
                self.assertEqual(json.loads(launch.call_args.args[0][3])['deadline_ns'], fault.config['deadline_ns'])
                close.assert_called_once_with(7)
                with self.assertRaises(AssertionError):
                    fault.arm()

    def test_injection_requires_pending_press_fresh_gate_live_watchdog(self):
        for failure in (None, 'done', 'stale', 'watchdog', 'deadline', 'lost_reply'):
            fault = self.controller()
            if failure == 'watchdog':
                fault.child.poll.return_value = 0
            if failure == 'deadline':
                fault.config['deadline_ns'] = 1
            with ExitStack() as stack:
                stack.enter_context(patch.object(proof, '_locked', side_effect=lambda _: nullcontext()))
                stack.enter_context(patch.object(proof, 'poll_active', return_value=(trace(ACTIVE), {1: 2})))
                stack.enter_context(patch.object(proof.time, 'monotonic_ns', side_effect=[5, 300_000_006 if failure == 'stale' else 6, 7]))
                replace = stack.enter_context(patch.object(proof, '_replace', side_effect=lambda *_args, **kwargs: kwargs['before_replace']()))
                stack.enter_context(patch.object(proof, '_reload', side_effect=TimeoutError('lost') if failure == 'lost_reply' else lambda *_: status(False)))
                stack.enter_context(patch.object(proof, 'file_identity', return_value={'sha256': proof.digest(proof.DISABLED.encode())}))
                if failure:
                    with self.assertRaises((AssertionError, TimeoutError)):
                        fault.inject(Mock(), trace(ACTIVE[:1]), Mock(done=Mock(return_value=failure == 'done')), Mock())
                else:
                    fault.inject(Mock(), trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), Mock())
                    self.assertEqual(fault.record['result'], 'observed')
                self.assertEqual(replace.call_count, int(failure != 'watchdog'))
                self.assertEqual(fault.mutated, failure in (None, 'lost_reply'))
                if failure == 'lost_reply':
                    self.assertTrue(fault.mutated)

    def test_motion_gate_controls_both_faults_without_replay(self):
        for kind in ('config_disable', 'keymap'):
            for failure in (None, 'done', 'done_after_motion', 'coordinates', 'identity', 'insufficient'):
                with self.subTest(kind=kind, failure=failure), ExitStack() as stack:
                    fault = self.controller()
                    fault.config.update(kind=kind, min_motion_px=12, instance='exact')
                    page = motion_trace(1 if failure == 'insufficient' else 12)
                    if failure == 'coordinates':
                        del page['events'][-1][7:9]
                    if failure == 'identity':
                        page['events'][-1][5] = 2
                    ticks = count()
                    stack.enter_context(patch.object(proof.time, 'monotonic', side_effect=lambda: next(ticks) / 100))
                    stack.enter_context(patch.object(proof.time, 'monotonic_ns', side_effect=[5_000_000, 6_000_000, 10_000_000]))
                    stack.enter_context(patch.object(proof, '_locked', side_effect=lambda _: nullcontext()))
                    gate = keymap_status(1)
                    gate['input']['lanes'][0].update(drag_active=True, lease_active=True, held_button=272)
                    fault.record['before'] = keymap_status(1)
                    stack.enter_context(patch.object(proof, 'production_status', return_value=gate))
                    stack.enter_context(patch.object(proof, 'keymap_options', side_effect=[options(), options(False)]))
                    stack.enter_context(patch.object(proof, 'file_identity', return_value={}))
                    # Match _replace's authorization boundary, without touching a file.
                    atomic = Mock()
                    def replace(*_args, **kwargs):
                        kwargs['before_replace']()
                        atomic()
                    stack.enter_context(patch.object(proof, '_replace', side_effect=replace))
                    reload = stack.enter_context(patch.object(proof, '_reload', return_value=keymap_status(2)
                                                             if kind == 'keymap' else status(False)))
                    pending = Mock(done=Mock(side_effect=[False, True]) if failure == 'done_after_motion'
                                   else Mock(return_value=failure == 'done'))
                    if failure:
                        with self.assertRaises(AssertionError):
                            fault.inject(Mock(collect=Mock(return_value=page)), trace(ACTIVE[:1]), pending, Mock())
                        atomic.assert_not_called()
                        reload.assert_not_called()
                        self.assertFalse(fault.mutated)
                    else:
                        fault.inject(Mock(collect=Mock(return_value=page)), trace(ACTIVE[:1]), pending, Mock())
                        atomic.assert_called_once()
                        reload.assert_called_once()
                        self.assertTrue(fault.mutated)
                        self.assertEqual(fault.record['prefix'], page)

    def test_keymap_injection_checks_active_native_gate_and_observed_generation(self):
        for failure in (None, 'gate_changed', 'gate_released', 'not_compiled', 'wrong_options'):
            with self.subTest(failure=failure), ExitStack() as stack:
                fault = self.controller()
                fault.config.update(kind='keymap', instance='exact')
                fault.record = {'kind': 'keymap', 'result': 'unproven', 'before': keymap_status(1)}
                gate = keymap_status(2 if failure == 'gate_changed' else 1)
                gate['input']['lanes'][0].update(drag_active=True, lease_active=True,
                                                held_button=0 if failure == 'gate_released' else 272)
                stack.enter_context(patch.object(proof, 'production_status', return_value=gate))
                stack.enter_context(patch.object(proof, 'keymap_options', side_effect=[options(),
                    AssertionError('wrong options') if failure == 'wrong_options' else options(False)]))
                stack.enter_context(patch.object(proof, '_locked', side_effect=lambda _: nullcontext()))
                stack.enter_context(patch.object(proof, 'poll_active', return_value=(trace(ACTIVE), {1: 2})))
                stack.enter_context(patch.object(proof.time, 'monotonic_ns', side_effect=[5, 6, 7]))
                replace = stack.enter_context(patch.object(proof, '_replace', side_effect=lambda *_args, **kwargs: kwargs['before_replace']()))
                stack.enter_context(patch.object(proof, '_reload', return_value=keymap_status(1 if failure == 'not_compiled' else 2)))
                stack.enter_context(patch.object(proof, 'file_identity', return_value={'sha256': proof.digest(proof.KEYMAP_CAPS_CTRL.encode())}))
                if failure:
                    with self.assertRaises(AssertionError):
                        fault.inject(Mock(), trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), Mock())
                else:
                    fault.inject(Mock(), trace(ACTIVE[:1]), Mock(done=Mock(return_value=False)), Mock())
                    self.assertEqual(fault.record['result'], 'observed')
                    self.assertEqual(fault.record['keymap_after'], options(False))
                self.assertEqual(replace.call_count, int(failure not in ('gate_changed', 'gate_released')))
                self.assertEqual(fault.mutated, failure not in ('gate_changed', 'gate_released'))

    def test_failed_restore_never_cancels_watchdog_or_deletes_backup(self):
        fault = self.controller()
        fault.mutated = True
        fault._clean_staged = Mock()
        with patch.object(proof, 'restore_config', side_effect=RuntimeError('unowned config')), \
             patch.object(proof.os, 'write') as write, patch.object(proof.os, 'close') as close:
            with self.assertRaises(RuntimeError):
                fault.close()
        write.assert_not_called()
        close.assert_called_once_with(8)
        fault._clean_staged.assert_not_called()

    def test_watchdog_eof_and_timeout_restore_cancel_does_not(self):
        for ready, data in (([], b''), ([8], b''), ([8], b'C')):
            with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
                config = {'deadline_ns': 1, 'record': str(Path(root) / 'watchdog.json')}
                stack.enter_context(patch.object(proof, '_guard'))
                stack.enter_context(patch.object(proof.select, 'select', return_value=(ready, [], [])))
                stack.enter_context(patch.object(proof.os, 'read', return_value=data))
                restore = stack.enter_context(patch.object(proof, 'restore_config', return_value=restoration()))
                stack.enter_context(patch('builtins.print'))
                proof.watchdog(config, 8)
                self.assertEqual(restore.call_count, int(data != b'C'))
                self.assertTrue(Path(config['record']).exists())


class RunnerTests(unittest.TestCase):
    def test_invalid_plan_fails_before_native_controller_or_allocation(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            path = directory / 'plan.json'
            path.write_text(json.dumps({**plan(), 'disposable': False}))
            args = SimpleNamespace(plan=path, evidence=directory / 'evidence')
            with patch.object(proof, 'ConfigFault') as controller, patch.object(proof, 'DirectMCP') as launch, patch('builtins.print'):
                self.assertEqual(proof.run(args), 1)
            controller.assert_not_called()
            launch.assert_not_called()

    def test_retired_retained_plan_fails_before_native_controller_or_allocation(self):
        for kind in ('config_disable', 'keymap'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                directory = Path(root)
                path = directory / 'plan.json'
                candidate = plan(kind)
                candidate['fault']['pointer_cleanup'] = 'retained_inert'
                path.write_text(json.dumps(candidate))
                args = SimpleNamespace(plan=path, evidence=directory / 'evidence')
                with patch.object(proof, 'ConfigFault') as controller, patch.object(proof, 'DirectMCP') as launch, \
                        patch('builtins.print'):
                    self.assertEqual(proof.run(args), 1)
                controller.assert_not_called()
                launch.assert_not_called()
                report = json.loads((args.evidence / 'result.json').read_text())
                self.assertIn('retained_inert retired', report['error'])

    def test_reconnect_without_reset_restore_before_snapshot_and_new_action(self):
        # Every case uses the only certifiable policy, 'cleared' (#4257).
        cases = [(kind, failure, 'cleared') for kind in ('config_disable', 'keymap') for failure in (None, 'inject', 'restore', 'recovery')]
        cases += [('keymap', 'cancel', 'cleared')]
        for kind, failure, policy in cases:
            with self.subTest(kind=kind, failure=failure, policy=policy), tempfile.TemporaryDirectory() as root, ExitStack() as stack:
                directory = Path(root)
                path = directory / 'plan.json'
                candidate = plan(kind)
                path.write_text(json.dumps(candidate))
                args = SimpleNamespace(plan=path, evidence=directory / 'evidence', driver=Path('/driver'),
                    primary_grab=Path('/grab'), foreground_journal=Path('/journal'), trace_socket=Path('/cua-input-v3.sock'))
                order = []
                cancelled = trace(CANCEL)
                fault_record = keymap_record() if kind == 'keymap' else record()
                restored = keymap_restoration() if kind == 'keymap' else restoration()
                fault = Mock(record=fault_record, config={'instance': 'exact', 'pointer_cleanup': policy, 'lane': 1})
                def inject(*_):
                    order.append('inject')
                    if failure == 'inject':
                        raise AssertionError('injection failed')
                    return trace(ACTIVE), 1
                fault.inject.side_effect = inject
                def restore():
                    order.append('restore')
                    if failure == 'restore':
                        raise AssertionError('restore failed')
                    return restored
                fault.restore.side_effect = restore
                stack.enter_context(patch.object(proof, 'ConfigFault', return_value=fault))
                stack.enter_context(patch.object(proof, 'provenance', return_value={'files': {}}))
                agent, observer, fresh = client(100), client(101), client(102)
                agent.tool.return_value = {}
                observer.tool.return_value = {'structuredContent': {'screen_width': 1920, 'screen_height': 1080}}
                stack.enter_context(patch.object(proof, 'DirectMCP', side_effect=[agent, observer, fresh]))
                def snapshot(*_args, **_kwargs):
                    order.append('snapshot')
                    return target_snapshot('snapshot-' + str(len(order)), runtime=101, observed_ns=14_000_000)
                stack.enter_context(patch.object(proof, 'grounded_snapshot', side_effect=snapshot))
                stack.enter_context(patch.object(proof, 'prepare_drag', return_value={'snapshot': target_snapshot('prepared')}))
                stack.enter_context(patch.object(proof, 'production_status', return_value=restored['status']))
                stack.enter_context(patch.object(proof, 'call_drag', return_value=action()))
                grab = Mock(poll=Mock(return_value=None))
                grab.terminate.side_effect = lambda: setattr(grab.poll, 'return_value', 0)
                stack.enter_context(patch.object(proof.subprocess, 'Popen', return_value=grab))
                stack.enter_context(patch.object(proof, 'stop_process'))
                stack.enter_context(patch.object(proof, 'primary_acknowledgement', return_value='HELD\n'))
                stack.enter_context(patch.object(proof, 'wait_for', return_value=True))
                stack.enter_context(patch.object(proof, 'wm', return_value={'pid': 10}))
                stack.enter_context(patch.object(proof, 'state', return_value={'held': True, 'clicks': 0, 'keys': 0, 'scroll': 0}))
                stack.enter_context(patch.object(proof, 'require_primary_active'))
                stack.enter_context(patch.object(proof.time, 'monotonic_ns', side_effect=[0, 0, 0, 11_500_000]))
                first = Mock(hello={'protocol': 3}, collect=Mock(side_effect=[trace(ACTIVE[:1]), trace(ACTIVE) if failure == 'cancel' else cancelled]))
                page = deepcopy(cancelled)
                for ms, event, value in ((14, 'agent_admitted', 0), (15, 'pointer_button', 1),
                                         (16, 'pointer_button', 0), (17, 'agent_action_end', 0)):
                    page['events'].append([len(page['events']) + 1, ms * 1_000_000, event, 100, 100, 1, value])
                page['count'] = len(page['events'])
                last = proof.stopped_prefix(page if failure is None else cancelled)
                observations = [cancelled, cancelled, last]
                second = Mock(hello={'protocol': 3}, collect=Mock(side_effect=observations))
                stack.enter_context(patch.object(proof, 'connect_trace', side_effect=[first, second]))
                def recover(*args):
                    order.append('recovery')
                    if failure == 'recovery':
                        raise AssertionError('recovery failed')
                    args[-1]['result'] = 'verified'
                    return page
                stack.enter_context(patch.object(proof, 'recover', side_effect=recover))
                stack.enter_context(patch.object(proof, 'close_owned', side_effect=lambda c: setattr(c.process.poll, 'return_value', 0)))
                stack.enter_context(patch('builtins.print'))
                self.assertEqual(proof.run(args), int(failure is not None))
                fault.close.assert_called_once()
                first.exchange.assert_any_call('TRACE_START')
                self.assertFalse(any(call.args == ('TRACE_START',) for call in second.exchange.call_args_list))
                self.assertEqual(agent.process.poll(), 0)
                self.assertEqual(observer.process.poll(), 0)
                if failure not in ('inject', 'restore', 'cancel'):
                    self.assertLess(order.index('restore'), len(order) - 1 - order[::-1].index('snapshot'))
                    self.assertLess(order.index('restore'), order.index('recovery'))
                    self.assertTrue((args.evidence / 'pre-recovery-prefix.json').is_file())
                    self.assertFalse((args.evidence / 'interrupted-status.json').exists())
                report = json.loads((args.evidence / 'result.json').read_text())
                self.assertFalse(report['full_desktop_matrix'])
                self.assertFalse(report['physical_hardware'])


if __name__ == '__main__':
    unittest.main()
