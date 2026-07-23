from __future__ import annotations

import random
import threading
import unittest
from unittest.mock import patch as mock_patch

import numpy as np
import torch

import src.external_replication.rng as rng_module

from src.external_replication.rng import (
    GLOBAL_RNG_BLOCK_MESSAGE,
    MULTIPROCESS_POISONING,
    MULTITHREADED_STRUCTURAL_POISONING,
    MULTIWORKER_DATALOADER_POISONING,
    NESTED_POISON_GUARD,
    NUMPY_GLOBAL_RNG_APIS,
    OVERLAPPING_THREAD_POISON_GUARD,
    PYTHON_GLOBAL_RNG_APIS,
    REAL_EEGNET_INITIALIZATION_RNG,
    SINGLE_THREAD_POISON_GUARD,
    STANDARD_NN_MODULE_INITIALIZATION_CONTROL,
    TORCH_BLOCKED_GLOBAL_RNG_APIS,
    TORCH_EXPLICIT_GENERATOR_APIS,
    TORCH_PRIVATE_GENERATOR_PRIMITIVE,
    FatalRNGGuardError,
    GlobalRngStateContaminationError,
    RngOwner,
    RngOwnershipError,
    RngRegistry,
    global_rng_poison_guard,
    torch_model_seed_isolation,
)


class OwnedRngTests(unittest.TestCase):
    def test_same_explicit_owner_and_seed_reproduce_across_registries(self):
        left = RngRegistry().create(RngOwner.SUBSET_CHAIN).generator.integers(0, 1000, 20)
        right = RngRegistry().create(RngOwner.SUBSET_CHAIN).generator.integers(0, 1000, 20)
        np.testing.assert_array_equal(left, right)

    def test_different_owners_do_not_share_generator_instances(self):
        registry = RngRegistry()
        left = registry.create(RngOwner.DATA_SPLIT)
        right = registry.create(RngOwner.SUBSET_CHAIN)
        self.assertIsNot(left.generator, right.generator)

    def test_owner_can_only_initialize_once_per_registry(self):
        registry = RngRegistry()
        registry.create(RngOwner.RQ2_PRIMARY_PERMUTATION)
        with self.assertRaises(RngOwnershipError):
            registry.create(RngOwner.RQ2_PRIMARY_PERMUTATION)

    def test_advancing_stream_does_not_reseed(self):
        stream = RngRegistry().create(RngOwner.RQ2_PRIMARY_BOOTSTRAP).generator
        first = stream.integers(0, 2**31, 16)
        second = stream.integers(0, 2**31, 16)
        self.assertFalse(np.array_equal(first, second))

    def test_unrelated_owned_stream_consumption_has_no_effect(self):
        registry = RngRegistry()
        target = registry.create(RngOwner.RQ2_REFINED_PERMUTATION).generator
        unrelated = registry.create(RngOwner.RQ2_PRIMARY_PERMUTATION).generator
        unrelated.integers(0, 100, 10000)
        observed = target.integers(0, 100, 20)
        expected = RngRegistry().create(RngOwner.RQ2_REFINED_PERMUTATION).generator.integers(0, 100, 20)
        np.testing.assert_array_equal(observed, expected)

    def test_global_rng_poison_reference_operation(self):
        expected = RngRegistry().create(RngOwner.DATA_SPLIT).generator.permutation(50)
        np.random.seed(99)
        np.random.random(10000)
        random.seed(99)
        [random.random() for _ in range(10000)]
        torch.rand(1000)
        observed = RngRegistry().create(RngOwner.DATA_SPLIT).generator.permutation(50)
        np.testing.assert_array_equal(observed, expected)


class GlobalRngPoisonGuardTests(unittest.TestCase):
    @staticmethod
    def api_references():
        references = {}
        for name in PYTHON_GLOBAL_RNG_APIS:
            references[("python", name)] = getattr(random, name)
        for name in NUMPY_GLOBAL_RNG_APIS:
            references[("numpy", name)] = getattr(np.random, name)
        for name in TORCH_BLOCKED_GLOBAL_RNG_APIS + TORCH_EXPLICIT_GENERATOR_APIS:
            references[("torch", name)] = getattr(torch, name)
        return references

    def assert_blocked(self, operation):
        with self.assertRaisesRegex(RuntimeError, GLOBAL_RNG_BLOCK_MESSAGE):
            with global_rng_poison_guard():
                operation()

    def test_numpy_seed_blocked(self):
        self.assert_blocked(lambda: np.random.seed(1))

    def test_numpy_consumption_blocked(self):
        self.assert_blocked(lambda: np.random.random())

    def test_python_seed_blocked(self):
        self.assert_blocked(lambda: random.seed(1))

    def test_python_consumption_blocked(self):
        self.assert_blocked(lambda: random.random())

    def test_torch_seed_blocked(self):
        self.assert_blocked(lambda: torch.manual_seed(1))

    def test_torch_consumption_blocked_without_private_generator(self):
        self.assert_blocked(lambda: torch.rand(2))

    def test_private_pcg64_generator_survives(self):
        with global_rng_poison_guard():
            values = np.random.Generator(np.random.PCG64(7)).permutation(20)
        self.assertEqual(values.shape, (20,))

    def test_private_torch_generator_survives(self):
        with global_rng_poison_guard():
            with torch_model_seed_isolation(42) as generator:
                values = torch.rand(4, generator=generator)
        self.assertEqual(tuple(values.shape), (4,))

    def test_compliant_operation_preserves_ambient_states(self):
        python_before = random.getstate()
        numpy_before = np.random.get_state()
        torch_before = torch.get_rng_state().clone()
        with global_rng_poison_guard():
            RngRegistry().create(RngOwner.SUBSET_CHAIN).generator.integers(0, 100, 20)
        self.assertEqual(random.getstate(), python_before)
        self.assertTrue(np.array_equal(np.random.get_state()[1], numpy_before[1]))
        self.assertTrue(torch.equal(torch.get_rng_state(), torch_before))

    def test_cached_third_party_global_reference_is_detected(self):
        cached_global_numpy_call = np.random.random
        with self.assertRaisesRegex(GlobalRngStateContaminationError, "GLOBAL_RNG_STATE_CONTAMINATION"):
            with global_rng_poison_guard():
                cached_global_numpy_call(4)

    def test_guard_contract_statuses_are_explicit(self):
        self.assertEqual(SINGLE_THREAD_POISON_GUARD, "SUPPORTED")
        self.assertEqual(NESTED_POISON_GUARD, "UNSUPPORTED_FAIL_CLOSED")
        self.assertEqual(OVERLAPPING_THREAD_POISON_GUARD, "UNSUPPORTED_FAIL_CLOSED")
        self.assertEqual(
            MULTITHREADED_STRUCTURAL_POISONING,
            "UNSUPPORTED_FAIL_CLOSED_PHASE_I",
        )
        self.assertEqual(
            MULTIWORKER_DATALOADER_POISONING,
            "UNSUPPORTED_FAIL_CLOSED_PHASE_I",
        )
        self.assertEqual(MULTIPROCESS_POISONING, "UNSUPPORTED_PHASE_I")

    def test_every_patched_api_is_restored_by_exact_identity(self):
        originals = self.api_references()
        with global_rng_poison_guard():
            patched = self.api_references()
            self.assertEqual(set(patched), set(originals))
            self.assertTrue(
                all(patched[key] is not originals[key] for key in originals)
            )
        restored = self.api_references()
        self.assertEqual(set(restored), set(originals))
        self.assertTrue(all(restored[key] is originals[key] for key in originals))

    def test_same_thread_nesting_fails_closed_and_restores(self):
        originals = self.api_references()
        with global_rng_poison_guard():
            with self.assertRaisesRegex(
                FatalRNGGuardError, "strictly forbidden"
            ):
                with global_rng_poison_guard():
                    self.fail("nested guard entered")
            with self.assertRaisesRegex(RuntimeError, GLOBAL_RNG_BLOCK_MESSAGE):
                random.random()
        self.assertEqual(self.api_references(), originals)
        with global_rng_poison_guard():
            pass

    def test_overlapping_thread_guard_fails_closed(self):
        originals = self.api_references()
        attempted = threading.Event()
        results = []

        def competing_guard():
            try:
                with global_rng_poison_guard():
                    results.append("ENTERED")
            except Exception as exc:
                results.append(exc)
            finally:
                attempted.set()

        with global_rng_poison_guard():
            worker = threading.Thread(target=competing_guard)
            worker.start()
            self.assertTrue(attempted.wait(5))
            worker.join(5)
            self.assertEqual(len(results), 1)
            self.assertIsInstance(results[0], FatalRNGGuardError)
            with self.assertRaisesRegex(RuntimeError, GLOBAL_RNG_BLOCK_MESSAGE):
                random.random()
        self.assertEqual(self.api_references(), originals)
        self.assertIsInstance(random.random(), float)
        with global_rng_poison_guard():
            pass

    def test_unrelated_body_exception_restores_and_releases_ownership(self):
        originals = self.api_references()
        python_before = random.getstate()
        numpy_before = np.random.get_state()
        torch_before = torch.get_rng_state().clone()
        with self.assertRaisesRegex(RuntimeError, "unrelated body failure"):
            with global_rng_poison_guard():
                raise RuntimeError("unrelated body failure")
        self.assertEqual(self.api_references(), originals)
        self.assertEqual(random.getstate(), python_before)
        self.assertTrue(np.array_equal(np.random.get_state()[1], numpy_before[1]))
        self.assertTrue(torch.equal(torch.get_rng_state(), torch_before))
        with global_rng_poison_guard():
            pass

    def test_poison_exception_restores_and_releases_ownership(self):
        originals = self.api_references()
        with self.assertRaisesRegex(RuntimeError, GLOBAL_RNG_BLOCK_MESSAGE):
            with global_rng_poison_guard():
                np.random.random()
        self.assertEqual(self.api_references(), originals)
        self.assertIsInstance(np.random.random(), float)
        with global_rng_poison_guard():
            pass

    def test_partial_patch_setup_failure_restores_and_releases_ownership(self):
        originals = self.api_references()

        def fail_after_one_patch(stack, _torch):
            stack.enter_context(
                mock_patch.object(random, "random", rng_module._blocked)
            )
            raise RuntimeError("synthetic partial patch failure")

        with mock_patch.object(
            rng_module, "_install_global_rng_patches", fail_after_one_patch
        ):
            with self.assertRaisesRegex(RuntimeError, "partial patch failure"):
                with global_rng_poison_guard():
                    self.fail("guard body entered after setup failure")
        self.assertEqual(self.api_references(), originals)
        with global_rng_poison_guard():
            pass


class TorchIsolationTests(unittest.TestCase):
    def test_real_module_initialization_boundary_is_explicitly_deferred(self):
        self.assertEqual(
            TORCH_PRIVATE_GENERATOR_PRIMITIVE,
            "IMPLEMENTED_FOR_EXPLICIT_DRAWS",
        )
        self.assertEqual(
            STANDARD_NN_MODULE_INITIALIZATION_CONTROL,
            "NOT_YET_IMPLEMENTED",
        )
        self.assertEqual(
            REAL_EEGNET_INITIALIZATION_RNG,
            "DEFERRED_TO_TRAINING_ENGINE_INTEGRATION",
        )

    def test_private_generator_does_not_claim_standard_module_initialization(self):
        torch.manual_seed(100)
        with torch_model_seed_isolation(42):
            first = torch.nn.Linear(4, 3).weight.detach().clone()
        torch.manual_seed(200)
        with torch_model_seed_isolation(42):
            second = torch.nn.Linear(4, 3).weight.detach().clone()
        self.assertFalse(torch.equal(first, second))

    def test_ambient_cpu_state_restored(self):
        before = torch.get_rng_state().clone()
        with torch_model_seed_isolation(42) as generator:
            torch.rand(10, generator=generator)
        self.assertTrue(torch.equal(torch.get_rng_state(), before))

    def test_prior_ambient_draws_do_not_change_private_sequence(self):
        with torch_model_seed_isolation(43) as generator:
            expected = torch.randn(10, generator=generator)
        torch.randn(1000)
        with torch_model_seed_isolation(43) as generator:
            observed = torch.randn(10, generator=generator)
        self.assertTrue(torch.equal(observed, expected))


if __name__ == "__main__":
    unittest.main()
