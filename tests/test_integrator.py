"""Tests for Integrator module."""

import pytest
from agents.architect.integrator import Integrator


class TestIntegrator:
    def test_init(self):
        integrator = Integrator(gh=None)
        assert integrator.gh is None

    def test_merge_branches(self):
        integrator = Integrator(gh=None)
        result = integrator.merge_branches("main", [])
        assert isinstance(result, bool)
