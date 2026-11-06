import os
import pytest

from security.auth import TokenAuth
from security.signing import PayloadSigner
import security.signed_trace as signed_trace_module


SYNTHETIC_DEV_SECRET = "synthetic-dev-secret-key-32chars"
SYNTHETIC_STAGE_SECRET = "synthetic-stage-secret-key-32chars"
SYNTHETIC_PROD_SECRET = "synthetic-prod-secret-key-32chars"
KNOWN_DEV_FALLBACK_JWT = "default-jwt-secret-change-in-prod"
KNOWN_DEV_FALLBACK_SSPL = "default-secret-key-change-in-prod"
KNOWN_DEV_FALLBACK_LINEAGE = "pravah-sovereign-lineage-key"
LITERAL_PLACEHOLDER = "##CONFIRM_STAGE_SECRET_WITH_PLATFORM_OWNER##"


@pytest.fixture(autouse=True)
def clean_environment_fixture(monkeypatch):
    """Ensure environment is always clean and restored to dev after every test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
    os.environ["ENVIRONMENT"] = "dev"


# ==============================================================================
# 1. JWT Authentication Fail-Closed Tests (10 scenarios)
# ==============================================================================
class TestJWTAuthenticationSecurity:
    def test_jwt_valid_synthetic_dev_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.setenv("JWT_SECRET_KEY", SYNTHETIC_DEV_SECRET)
        auth = TokenAuth()
        assert auth.secret_key == SYNTHETIC_DEV_SECRET
        token = auth.generate_token("dev_user")
        assert auth.verify_token(token)["valid"] is True

    def test_jwt_dev_allows_safe_built_in_fallback(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        auth = TokenAuth()
        assert auth.secret_key == KNOWN_DEV_FALLBACK_JWT
        token = auth.generate_token("dev_user")
        assert auth.verify_token(token)["valid"] is True

    def test_jwt_valid_synthetic_stage_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("JWT_SECRET_KEY", SYNTHETIC_STAGE_SECRET)
        auth = TokenAuth()
        assert auth.secret_key == SYNTHETIC_STAGE_SECRET
        token = auth.generate_token("stage_user")
        assert auth.verify_token(token)["valid"] is True

    def test_jwt_valid_synthetic_prod_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("JWT_SECRET_KEY", SYNTHETIC_PROD_SECRET)
        auth = TokenAuth()
        assert auth.secret_key == SYNTHETIC_PROD_SECRET
        token = auth.generate_token("prod_user")
        assert auth.verify_token(token)["valid"] is True

    def test_jwt_missing_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="staging"):
            TokenAuth()

    def test_jwt_empty_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("JWT_SECRET_KEY", "")
        with pytest.raises(ValueError, match="staging"):
            TokenAuth()

    def test_jwt_whitespace_only_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("JWT_SECRET_KEY", "   \t  \n ")
        with pytest.raises(ValueError, match="staging"):
            TokenAuth()

    def test_jwt_known_dev_fallback_in_staging_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("JWT_SECRET_KEY", KNOWN_DEV_FALLBACK_JWT)
        with pytest.raises(ValueError, match="staging"):
            TokenAuth()

    def test_jwt_literal_placeholder_in_staging_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("JWT_SECRET_KEY", LITERAL_PLACEHOLDER)
        with pytest.raises(ValueError, match="staging"):
            TokenAuth()

    def test_jwt_missing_production_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="production"):
            TokenAuth()

    def test_jwt_invalid_environment_name_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stag_invalid")
        monkeypatch.setenv("JWT_SECRET_KEY", SYNTHETIC_STAGE_SECRET)
        with pytest.raises(ValueError, match="Invalid or unsupported ENVIRONMENT"):
            TokenAuth()


# ==============================================================================
# 2. SSPL Payload Signing Fail-Closed Tests (10 scenarios)
# ==============================================================================
class TestSSPLSigningSecurity:
    def test_sspl_valid_synthetic_dev_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.setenv("SSPL_SECRET_KEY", SYNTHETIC_DEV_SECRET)
        signer = PayloadSigner()
        assert signer.secret_key == SYNTHETIC_DEV_SECRET
        signed = signer.sign_payload({"event": "dev_test"})
        assert signer.verify_payload(signed) is True

    def test_sspl_dev_allows_safe_built_in_fallback(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.delenv("SSPL_SECRET_KEY", raising=False)
        signer = PayloadSigner()
        assert signer.secret_key == KNOWN_DEV_FALLBACK_SSPL
        signed = signer.sign_payload({"event": "dev_fallback"})
        assert signer.verify_payload(signed) is True

    def test_sspl_valid_synthetic_stage_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("SSPL_SECRET_KEY", SYNTHETIC_STAGE_SECRET)
        signer = PayloadSigner()
        assert signer.secret_key == SYNTHETIC_STAGE_SECRET
        signed = signer.sign_payload({"event": "stage_test"})
        assert signer.verify_payload(signed) is True

    def test_sspl_valid_synthetic_prod_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("SSPL_SECRET_KEY", SYNTHETIC_PROD_SECRET)
        signer = PayloadSigner()
        assert signer.secret_key == SYNTHETIC_PROD_SECRET
        signed = signer.sign_payload({"event": "prod_test"})
        assert signer.verify_payload(signed) is True

    def test_sspl_missing_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.delenv("SSPL_SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="staging"):
            PayloadSigner()

    def test_sspl_empty_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("SSPL_SECRET_KEY", "")
        with pytest.raises(ValueError, match="staging"):
            PayloadSigner()

    def test_sspl_whitespace_only_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("SSPL_SECRET_KEY", "   \t  ")
        with pytest.raises(ValueError, match="staging"):
            PayloadSigner()

    def test_sspl_known_dev_fallback_in_staging_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("SSPL_SECRET_KEY", KNOWN_DEV_FALLBACK_SSPL)
        with pytest.raises(ValueError, match="staging"):
            PayloadSigner()

    def test_sspl_literal_placeholder_in_staging_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("SSPL_SECRET_KEY", LITERAL_PLACEHOLDER)
        with pytest.raises(ValueError, match="staging"):
            PayloadSigner()

    def test_sspl_missing_production_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("SSPL_SECRET_KEY", raising=False)
        with pytest.raises(ValueError, match="production"):
            PayloadSigner()

    def test_sspl_invalid_environment_name_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prodd_invalid")
        monkeypatch.setenv("SSPL_SECRET_KEY", SYNTHETIC_PROD_SECRET)
        with pytest.raises(ValueError, match="Invalid or unsupported ENVIRONMENT"):
            PayloadSigner()


# ==============================================================================
# 3. Lineage Signing Fail-Closed Tests (10 scenarios)
# ==============================================================================
class TestLineageSigningSecurity:
    def test_lineage_valid_synthetic_dev_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", SYNTHETIC_DEV_SECRET)
        key = signed_trace_module._resolve_lineage_key()
        assert key == SYNTHETIC_DEV_SECRET.encode("utf-8")

    def test_lineage_dev_allows_safe_built_in_fallback(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.delenv("LINEAGE_SIGNING_KEY", raising=False)
        key = signed_trace_module._resolve_lineage_key()
        assert key == KNOWN_DEV_FALLBACK_LINEAGE.encode("utf-8")

    def test_lineage_valid_synthetic_stage_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", SYNTHETIC_STAGE_SECRET)
        key = signed_trace_module._resolve_lineage_key()
        assert key == SYNTHETIC_STAGE_SECRET.encode("utf-8")

    def test_lineage_valid_synthetic_prod_config(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", SYNTHETIC_PROD_SECRET)
        key = signed_trace_module._resolve_lineage_key()
        assert key == SYNTHETIC_PROD_SECRET.encode("utf-8")

    def test_lineage_missing_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.delenv("LINEAGE_SIGNING_KEY", raising=False)
        with pytest.raises(ValueError, match="staging"):
            signed_trace_module._resolve_lineage_key()

    def test_lineage_empty_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", "")
        with pytest.raises(ValueError, match="staging"):
            signed_trace_module._resolve_lineage_key()

    def test_lineage_whitespace_only_staging_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", "  \n\t ")
        with pytest.raises(ValueError, match="staging"):
            signed_trace_module._resolve_lineage_key()

    def test_lineage_known_dev_fallback_in_staging_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", KNOWN_DEV_FALLBACK_LINEAGE)
        with pytest.raises(ValueError, match="staging"):
            signed_trace_module._resolve_lineage_key()

    def test_lineage_literal_placeholder_in_staging_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "stage")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", LITERAL_PLACEHOLDER)
        with pytest.raises(ValueError, match="staging"):
            signed_trace_module._resolve_lineage_key()

    def test_lineage_missing_production_secret_fails_closed(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.delenv("LINEAGE_SIGNING_KEY", raising=False)
        with pytest.raises(ValueError, match="production"):
            signed_trace_module._resolve_lineage_key()

    def test_lineage_invalid_environment_name_rejected(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "staging_misspelled")
        monkeypatch.setenv("LINEAGE_SIGNING_KEY", SYNTHETIC_STAGE_SECRET)
        with pytest.raises(ValueError, match="Invalid or unsupported ENVIRONMENT"):
            signed_trace_module._resolve_lineage_key()
