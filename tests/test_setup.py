"""Basic test to verify pytest is working."""


def test_pytest_works():
    """Verify pytest is properly configured and can run tests."""
    assert True


def test_imports():
    """Verify key modules can be imported."""
    import aggregators
    import card_aggregator
    import card_utils

    assert aggregators is not None
    assert card_aggregator is not None
    assert card_utils is not None
