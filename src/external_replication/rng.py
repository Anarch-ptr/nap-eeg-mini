"""Explicit RNG ownership and adversarial global-state protection."""

from __future__ import annotations

import contextlib
import random
import threading
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterator
from unittest.mock import patch

import numpy as np

from .constants import FROZEN_V1_CONSTANTS


class RngOwner(str, Enum):
    DATA_SPLIT = "DATA_SPLIT"
    SUBSET_CHAIN = "SUBSET_CHAIN"
    RQ2_PRIMARY_PERMUTATION = "RQ2_PRIMARY_PERMUTATION"
    RQ2_BASELINE_CAPABLE_PERMUTATION = "RQ2_BASELINE_CAPABLE_PERMUTATION"
    RQ2_REFINED_PERMUTATION = "RQ2_REFINED_PERMUTATION"
    RQ2_PRIMARY_BOOTSTRAP = "RQ2_PRIMARY_BOOTSTRAP"
    RQ2_BASELINE_CAPABLE_BOOTSTRAP = "RQ2_BASELINE_CAPABLE_BOOTSTRAP"
    RQ2_REFINED_BOOTSTRAP = "RQ2_REFINED_BOOTSTRAP"


REGISTERED_NUMPY_SEEDS = MappingProxyType({
    RngOwner.DATA_SPLIT: FROZEN_V1_CONSTANTS.split_seed,
    RngOwner.SUBSET_CHAIN: FROZEN_V1_CONSTANTS.subset_chain_seed,
    **{
        RngOwner[owner_name]: seed
        for owner_name, seed in (
            FROZEN_V1_CONSTANTS.rq2_permutation_seeds
            + FROZEN_V1_CONSTANTS.rq2_bootstrap_seeds
        )
    },
})
MODEL_SEEDS = FROZEN_V1_CONSTANTS.model_seeds
TORCH_PRIVATE_GENERATOR_PRIMITIVE = "IMPLEMENTED_FOR_EXPLICIT_DRAWS"
PRIVATE_TORCH_GENERATOR_DRAW_CONTROL = "IMPLEMENTED"
STANDARD_NN_MODULE_INITIALIZATION_CONTROL = "NOT_YET_IMPLEMENTED"
REAL_EEGNET_INITIALIZATION_RNG = "DEFERRED_TO_TRAINING_ENGINE_INTEGRATION"
REAL_TRAINING_RNG_LOCK_STATUS = "LOCK_REQUIRED_BEFORE_REAL_TRAINING"
TORCH_RNG_ISOLATION_VALIDATION = "CPU_REFERENCE_VALIDATED_CUDA_UNVALIDATED"

SINGLE_THREAD_POISON_GUARD = "SUPPORTED"
NESTED_POISON_GUARD = "UNSUPPORTED_FAIL_CLOSED"
OVERLAPPING_THREAD_POISON_GUARD = "UNSUPPORTED_FAIL_CLOSED"
MULTITHREADED_STRUCTURAL_POISONING = "UNSUPPORTED_FAIL_CLOSED_PHASE_I"
MULTIWORKER_DATALOADER_POISONING = "UNSUPPORTED_FAIL_CLOSED_PHASE_I"
MULTIPROCESS_POISONING = "UNSUPPORTED_PHASE_I"


@dataclass(frozen=True)
class OwnedNumpyRng:
    owner_name: RngOwner
    seed: int
    bit_generator_name: str
    generator: np.random.Generator


class RngOwnershipError(RuntimeError):
    pass


class RngRegistry:
    """One initialization per owner within one registered analysis lifecycle."""

    def __init__(self) -> None:
        self._streams: dict[RngOwner, OwnedNumpyRng] = {}

    def create(self, owner: RngOwner) -> OwnedNumpyRng:
        if owner in self._streams:
            raise RngOwnershipError(f"REGISTERED_RNG_ALREADY_INITIALIZED: {owner.value}")
        seed = REGISTERED_NUMPY_SEEDS[owner]
        stream = OwnedNumpyRng(
            owner_name=owner,
            seed=seed,
            bit_generator_name="PCG64",
            generator=np.random.Generator(np.random.PCG64(seed)),
        )
        self._streams[owner] = stream
        return stream


GLOBAL_RNG_BLOCK_MESSAGE = "GLOBAL RNG ACCESS BLOCKED BY PROTOCOL"


class GlobalRngStateContaminationError(RuntimeError):
    pass


class FatalRNGGuardError(RuntimeError):
    pass


PYTHON_GLOBAL_RNG_APIS = (
    "seed", "random", "randrange", "randint", "choice", "choices", "shuffle",
    "sample", "uniform",
)
NUMPY_GLOBAL_RNG_APIS = (
    "seed", "random", "random_sample", "rand", "randn", "randint", "choice",
    "shuffle", "permutation", "normal", "uniform",
)
TORCH_BLOCKED_GLOBAL_RNG_APIS = ("manual_seed", "seed", "multinomial")
TORCH_EXPLICIT_GENERATOR_APIS = ("rand", "randn", "randint", "randperm")

_GLOBAL_RNG_POISON_OWNERSHIP_LOCK = threading.Lock()


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError(GLOBAL_RNG_BLOCK_MESSAGE)


def _torch_block_unless_private_generator(original):
    def guarded(*args, **kwargs):
        if kwargs.get("generator") is None:
            raise RuntimeError(GLOBAL_RNG_BLOCK_MESSAGE)
        return original(*args, **kwargs)

    return guarded


def _numpy_state_equal(left: tuple, right: tuple) -> bool:
    return (
        left[0] == right[0]
        and np.array_equal(left[1], right[1])
        and left[2:] == right[2:]
    )


def _install_global_rng_patches(stack: contextlib.ExitStack, torch: object) -> None:
    """Install the deterministic patch registry under exclusive ownership."""

    for name in PYTHON_GLOBAL_RNG_APIS:
        stack.enter_context(patch.object(random, name, _blocked))
    for name in NUMPY_GLOBAL_RNG_APIS:
        stack.enter_context(patch.object(np.random, name, _blocked))
    for name in TORCH_BLOCKED_GLOBAL_RNG_APIS:
        stack.enter_context(patch.object(torch, name, _blocked))
    for name in TORCH_EXPLICIT_GENERATOR_APIS:
        stack.enter_context(
            patch.object(
                torch,
                name,
                _torch_block_unless_private_generator(getattr(torch, name)),
            )
        )


@contextlib.contextmanager
def global_rng_poison_guard() -> Iterator[None]:
    """Exclusively poison ambient RNG APIs for single-thread structural smoke.

    Nested, overlapping-thread, multiworker and multiprocess poisoning are not
    supported in Phase I.  A second process-local owner fails immediately before
    applying any patch.
    """

    if not _GLOBAL_RNG_POISON_OWNERSHIP_LOCK.acquire(blocking=False):
        raise FatalRNGGuardError(
            "Nested or concurrent RNG poisoning is strictly forbidden (fail-closed)."
        )
    try:
        import torch

        python_before = random.getstate()
        numpy_before = np.random.get_state()
        torch_before = torch.get_rng_state().clone()
        cuda_supported = bool(torch.cuda.is_available())
        cuda_before = torch.cuda.get_rng_state_all() if cuda_supported else None
        try:
            with contextlib.ExitStack() as stack:
                _install_global_rng_patches(stack, torch)
                yield
        finally:
            python_after = random.getstate()
            numpy_after = np.random.get_state()
            torch_after = torch.get_rng_state()
            cuda_after = torch.cuda.get_rng_state_all() if cuda_supported else None
            contaminated = (
                python_after != python_before
                or not _numpy_state_equal(numpy_after, numpy_before)
                or not torch.equal(torch_after, torch_before)
                or (
                    cuda_supported
                    and any(
                        not torch.equal(after, before)
                        for after, before in zip(cuda_after, cuda_before)
                    )
                )
            )
            if contaminated:
                random.setstate(python_before)
                np.random.set_state(numpy_before)
                torch.set_rng_state(torch_before)
                if cuda_supported:
                    torch.cuda.set_rng_state_all(cuda_before)
                raise GlobalRngStateContaminationError(
                    "GLOBAL_RNG_STATE_CONTAMINATION"
                )
    finally:
        _GLOBAL_RNG_POISON_OWNERSHIP_LOCK.release()


@contextlib.contextmanager
def torch_model_seed_isolation(model_seed: int) -> Iterator[object]:
    """Yield a private CPU Generator for explicit draws only.

    This does not control ordinary ``nn.Conv2d``/``nn.Linear`` initialization.
    Real EEGNet constructor RNG integration is deferred to the training engine
    and remains locked before real training.
    """

    import torch

    if model_seed not in MODEL_SEEDS:
        raise RngOwnershipError(f"UNREGISTERED_MODEL_SEED: {model_seed}")
    ambient_before = torch.get_rng_state().clone()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(model_seed)
    try:
        yield generator
    finally:
        if not torch.equal(torch.get_rng_state(), ambient_before):
            torch.set_rng_state(ambient_before)


GLOBAL_RNG_POISON_GUARD = global_rng_poison_guard
