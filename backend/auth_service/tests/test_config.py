import base64
import os
from unittest.mock import patch


SAMPLE_PRIVATE_PEM = "-----BEGIN PRIVATE KEY-----\nABCDEF\n-----END PRIVATE KEY-----\n"
SAMPLE_PUBLIC_PEM = "-----BEGIN PUBLIC KEY-----\nGHIJKL\n-----END PUBLIC KEY-----\n"


def _reimport_settings():
    """Reimport the settings module so env-var changes are picked up."""
    import importlib
    from auth_service.core import config as cfg_mod
    importlib.reload(cfg_mod)
    return cfg_mod.settings


def test_private_key_read_from_env_var_when_set():
    encoded = base64.b64encode(SAMPLE_PRIVATE_PEM.encode()).decode()
    with patch.dict(os.environ, {"JWT_PRIVATE_KEY_B64": encoded}):
        settings = _reimport_settings()
        assert settings.private_key == SAMPLE_PRIVATE_PEM


def test_public_key_read_from_env_var_when_set():
    encoded = base64.b64encode(SAMPLE_PUBLIC_PEM.encode()).decode()
    with patch.dict(os.environ, {"JWT_PUBLIC_KEY_B64": encoded}):
        settings = _reimport_settings()
        assert settings.public_key == SAMPLE_PUBLIC_PEM


def test_private_key_falls_back_to_file_when_env_unset():
    env_without = {k: v for k, v in os.environ.items() if k != "JWT_PRIVATE_KEY_B64"}
    with patch.dict(os.environ, env_without, clear=True):
        settings = _reimport_settings()
        content = settings.private_key
        assert "-----BEGIN" in content
