"""Keep synthetic referral persistence out of operator profile directories."""
import pytest


@pytest.fixture(autouse=True)
def synthetic_referral_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("FCM_REFERRALS_DIR", str(tmp_path / "referrals"))
