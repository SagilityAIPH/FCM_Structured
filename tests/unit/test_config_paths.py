from fcm_intake.config import CUSTOMERCHECKER_SCRIPT, FCM_SCRIPT, REOPENCHECK_SCRIPT


def test_configured_legacy_scripts_exist():
    assert FCM_SCRIPT.exists()
    assert CUSTOMERCHECKER_SCRIPT.exists()
    assert REOPENCHECK_SCRIPT.exists()
