import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("contracts", Path(__file__).with_name("python-contracts.py"))
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)


class ExtractorTests(unittest.TestCase):
    def test_new_enum_and_nullable_are_preserved(self):
        actual = contracts.parse_source('class Status(StrEnum):\n A="a"\n NEW="new"\nclass Dto(BaseModel):\n value: int | None\n flag: bool\n')
        self.assertEqual(actual["Status"]["values"], ["a", "new"])
        self.assertEqual(actual["Dto"]["fields"]["value"]["atoms"], ["null", "number"])
        self.assertEqual(actual["Dto"]["fields"]["flag"]["atoms"], ["boolean"])

    def test_extractor_never_imports_or_executes_supplied_source(self):
        self.assertEqual(contracts.parse_source('raise RuntimeError("must not execute")\n'), {})


if __name__ == "__main__":
    unittest.main()
