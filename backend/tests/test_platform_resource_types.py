import unittest

from shared.platform_resource_types import (
    PLATFORM_RESOURCE_TYPES,
    is_allowed_platform_resource_type,
    validate_platform_resource_type,
)


class PlatformResourceTypesTests(unittest.TestCase):
    def test_allowed_types(self) -> None:
        self.assertEqual(PLATFORM_RESOURCE_TYPES, ("file_store", "mcp", "metrics_platform"))

    def test_rejects_legacy_web(self) -> None:
        self.assertFalse(is_allowed_platform_resource_type("web"))
        with self.assertRaises(ValueError):
            validate_platform_resource_type("web")

    def test_accepts_mcp(self) -> None:
        self.assertEqual(validate_platform_resource_type("mcp"), "mcp")


if __name__ == "__main__":
    unittest.main()
