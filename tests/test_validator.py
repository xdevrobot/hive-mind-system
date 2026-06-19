"""Tests for Validator module."""

import pytest
from agents.architect.validator import Validator


class TestValidator:
    def test_init(self):
        validator = Validator(gh=None)
        assert validator.gh is None

    def test_validate_prerequisites(self):
        validator = Validator(gh=None)
        result = validator.validate_prerequisites()
        assert isinstance(result, bool)
