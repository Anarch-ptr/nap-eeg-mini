"""Fail-closed authorization and transport policy for Phase II-B acquisition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Protocol


class AuthorizationState(str, Enum):
    DENY = "DENY"
    ALLOW = "ALLOW"


class AcquisitionMode(str, Enum):
    ACQUISITION = "ACQUISITION"
    SCIENTIFIC_EXECUTION = "SCIENTIFIC_EXECUTION"


class NetworkFailureReason(str, Enum):
    ACQUISITION_NOT_AUTHORIZED = "ACQUISITION_NOT_AUTHORIZED"
    NETWORK_NOT_AUTHORIZED = "NETWORK_NOT_AUTHORIZED"
    SCIENTIFIC_EXECUTION_FORBIDS_ACQUISITION = (
        "SCIENTIFIC_EXECUTION_FORBIDS_ACQUISITION"
    )
    TRANSPORT_NOT_CONFIGURED = "TRANSPORT_NOT_CONFIGURED"


class NetworkPolicyError(RuntimeError):
    def __init__(self, reason: NetworkFailureReason):
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True)
class AcquisitionAuthorization:
    """Independent acquisition, network, and scientific authorization switches."""

    acquisition: AuthorizationState = AuthorizationState.DENY
    network: AuthorizationState = AuthorizationState.DENY
    scientific_execution: AuthorizationState = AuthorizationState.DENY

    @classmethod
    def explicitly_authorized_for_acquisition(
        cls,
    ) -> "AcquisitionAuthorization":
        return cls(
            acquisition=AuthorizationState.ALLOW,
            network=AuthorizationState.ALLOW,
            scientific_execution=AuthorizationState.DENY,
        )


@dataclass(frozen=True)
class TransportResponse:
    status: int
    chunks: Iterable[bytes]
    headers: Mapping[str, str] | None = None
    redirect_chain: tuple[str, ...] = ()
    transport_identifier: str = "INJECTED_TRANSPORT"


class DownloadTransport(Protocol):
    def open(self, source_url: str) -> TransportResponse:
        """Open a byte stream. Implementations must perform no implicit retries."""


@dataclass(frozen=True)
class NetworkPolicy:
    authorization: AcquisitionAuthorization = AcquisitionAuthorization()
    mode: AcquisitionMode = AcquisitionMode.ACQUISITION

    def authorize_acquisition(self) -> None:
        if self.mode is AcquisitionMode.SCIENTIFIC_EXECUTION:
            raise NetworkPolicyError(
                NetworkFailureReason.SCIENTIFIC_EXECUTION_FORBIDS_ACQUISITION
            )
        if self.authorization.acquisition is not AuthorizationState.ALLOW:
            raise NetworkPolicyError(
                NetworkFailureReason.ACQUISITION_NOT_AUTHORIZED
            )

    def authorize_network(self) -> None:
        """Validate both switches without requiring or constructing a transport."""
        self.authorize_acquisition()
        if self.authorization.network is not AuthorizationState.ALLOW:
            raise NetworkPolicyError(NetworkFailureReason.NETWORK_NOT_AUTHORIZED)

    def authorize_transport(self, transport: DownloadTransport | None) -> DownloadTransport:
        self.authorize_network()
        if transport is None:
            raise NetworkPolicyError(NetworkFailureReason.TRANSPORT_NOT_CONFIGURED)
        return transport
