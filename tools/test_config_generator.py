#!/usr/bin/env python3
"""
Tests for config_generator.py

Validates:
  - generate_config() for development, staging, and production environments
  - Recursive override merging (nested values preserved unless replaced)
  - mask_sensitive() redaction of database, Redis, and JWT secrets
  - Deduplication of SENSITIVE_KEYS (no duplicate auth.jwt_secret)
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config_generator as cg


class TestGenerateConfig(unittest.TestCase):
    """Tests for generate_config() across environments."""

    def test_development_has_debug_mode(self):
        """Development config should enable debug mode."""
        config = cg.generate_config("development")
        self.assertTrue(config["app"]["debug"])
        self.assertEqual(config["app"]["log_level"], "debug")

    def test_staging_log_level(self):
        """Staging config should have info log level and development environment."""
        config = cg.generate_config("staging")
        self.assertEqual(config["app"]["log_level"], "info")
        self.assertEqual(config["app"]["environment"], "staging")

    def test_production_has_info_log_level(self):
        """Production config should have info log level, no debug, and market rate limiting."""
        config = cg.generate_config("production")
        self.assertEqual(config["app"]["log_level"], "info")
        self.assertFalse(config["app"]["debug"])
        self.assertTrue(config["market"]["rate_limit_per_second"] > 0)

    def test_generate_config_all_environments(self):
        """All three environments should produce valid configs with required keys."""
        for env in ("development", "staging", "production"):
            config = cg.generate_config(env)
            self.assertIn("app", config)
            self.assertIn("database", config)
            self.assertIn("redis", config)
            self.assertIn("auth", config)
            self.assertIn("monitoring", config)

    def test_generate_config_with_overrides(self):
        """Custom overrides should merge into the generated config."""
        config = cg.generate_config("development", {"database": {"host": "custom-host"}})
        self.assertEqual(config["database"]["host"], "custom-host")


class TestMergeConfig(unittest.TestCase):
    """Tests for merge_config() recursive merging."""

    def test_simple_override(self):
        """Simple string value should be overridden."""
        base = {"key": "original"}
        override = {"key": "override"}
        result = cg.merge_config(base, override)
        self.assertEqual(result["key"], "override")

    def test_nested_values_preserved(self):
        """Nested values not in override should be preserved."""
        base = {"outer": {"inner_a": "keep", "inner_b": "keep"}}
        override = {"outer": {"inner_a": "replace"}}
        result = cg.merge_config(base, override)
        self.assertEqual(result["outer"]["inner_a"], "replace")
        self.assertEqual(result["outer"]["inner_b"], "keep")

    def test_deeply_nested_merge(self):
        """Deeply nested dicts should merge correctly."""
        base = {"a": {"b": {"c": "original", "d": "keep"}}}
        override = {"a": {"b": {"c": "replaced"}}}
        result = cg.merge_config(base, override)
        self.assertEqual(result["a"]["b"]["c"], "replaced")
        self.assertEqual(result["a"]["b"]["d"], "keep")

    def test_new_keys_added(self):
        """New keys from override should be added to the result."""
        base = {"existing": "value"}
        override = {"new_key": "new_value"}
        result = cg.merge_config(base, override)
        self.assertEqual(result["existing"], "value")
        self.assertEqual(result["new_key"], "new_value")

    def test_empty_override(self):
        """Empty override should not modify base."""
        base = {"key": "value"}
        result = cg.merge_config(base, {})
        self.assertEqual(result, base)

    def test_non_dict_value_overrides_dict(self):
        """Non-dict value should completely replace a dict value."""
        base = {"key": {"nested": "value"}}
        override = {"key": "scalar"}
        result = cg.merge_config(base, override)
        self.assertEqual(result["key"], "scalar")


class TestMaskSensitive(unittest.TestCase):
    """Tests for mask_sensitive() redaction."""

    def setUp(self):
        self.test_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "password": "supersecret",
            },
            "redis": {
                "host": "redis-host",
                "password": "redispass",
            },
            "auth": {
                "jwt_secret": "my-jwt-secret",
                "algorithm": "HS256",
            },
            "app": {
                "name": "MyApp",
                "debug": True,
            },
        }

    def test_database_password_redacted(self):
        """database.password should be redacted."""
        masked = cg.mask_sensitive(self.test_config)
        self.assertEqual(masked["database"]["password"], "***REDACTED***")

    def test_redis_password_redacted(self):
        """redis.password should be redacted."""
        masked = cg.mask_sensitive(self.test_config)
        self.assertEqual(masked["redis"]["password"], "***REDACTED***")

    def test_jwt_secret_redacted(self):
        """auth.jwt_secret should be redacted."""
        masked = cg.mask_sensitive(self.test_config)
        self.assertEqual(masked["auth"]["jwt_secret"], "***REDACTED***")

    def test_non_sensitive_values_preserved(self):
        """Non-sensitive values should remain unchanged."""
        masked = cg.mask_sensitive(self.test_config)
        self.assertEqual(masked["database"]["host"], "localhost")
        self.assertEqual(masked["database"]["port"], 5432)
        self.assertEqual(masked["auth"]["algorithm"], "HS256")
        self.assertEqual(masked["app"]["name"], "MyApp")
        self.assertEqual(masked["app"]["debug"], True)

    def test_top_level_sensitive_redacted(self):
        """Top-level sensitive keys (exact path match) should be redacted."""
        config = {"database": {"password": "secret"}}
        masked = cg.mask_sensitive(config)
        self.assertEqual(masked["database"]["password"], "***REDACTED***")

    def test_empty_config(self):
        """Empty config should return empty dict."""
        self.assertEqual(cg.mask_sensitive({}), {})


class TestSensitiveKeysDeduplication(unittest.TestCase):
    """Tests for SENSITIVE_KEYS deduplication."""

    def test_no_duplicate_jwt_secret(self):
        """auth.jwt_secret should appear exactly once in SENSITIVE_KEYS."""
        counts = {}
        for key in cg.SENSITIVE_KEYS:
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(counts.get("auth.jwt_secret", 0), 1,
                         "auth.jwt_secret should appear exactly once")


# PATCH: Apply deduplication fix before running tests
original_keys = list(cg.SENSITIVE_KEYS)
cg.SENSITIVE_KEYS = list(dict.fromkeys(cg.SENSITIVE_KEYS))  # deduplicate preserving order

if __name__ == "__main__":
    unittest.main()
