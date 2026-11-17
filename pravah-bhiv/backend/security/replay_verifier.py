from security.lineage_verifier import (
    LineageVerifier,
    ReplayIntegrityError,
)


class ReplayVerificationMiddleware:

    @staticmethod
    def verify_before_replay(
        replay_events,
        replay_payloads,
    ):
        try:

            LineageVerifier.verify_replay_chain(
                replay_events=replay_events,
                replay_payloads=replay_payloads,
            )

            return {
                "status": "VERIFIED",
                "replay_safe": True,
            }

        except ReplayIntegrityError as e:

            return {
                "status": "REJECTED",
                "replay_safe": False,
                "reason": str(e),
            }