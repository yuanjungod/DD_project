import unittest

from app.exceptions import ConflictError
from app.services.catalog_name_validation import assert_unique_name_in_index


class CatalogNameValidationTests(unittest.TestCase):
    def test_rejects_duplicate_name_case_insensitive(self) -> None:
        index = {"a": {"id": "a", "name": "文件库 A"}}
        with self.assertRaises(ConflictError):
            assert_unique_name_in_index(index, "文件库 a", label="Resource name")

    def test_allows_same_name_when_updating_self(self) -> None:
        index = {"a": {"id": "a", "name": "文件库 A"}}
        assert_unique_name_in_index(index, "文件库 A", exclude_id="a", label="Resource name")


if __name__ == "__main__":
    unittest.main()
