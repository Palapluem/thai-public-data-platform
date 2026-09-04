from thai_data_platform import PROJECT_NAME, __version__


def test_bootstrap_package_identity() -> None:
    assert PROJECT_NAME == "Thai Public Data Platform"
    assert __version__ == "0.1.0"
