"""Pytest configuration for SDK tests."""
import pytest


# SDK tests don't need a database - they test format conversion
# E2E tests that need backend should be run separately