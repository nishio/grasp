import unittest

from scripts import check_wiki_version_ledger as ledger


def pyproject(version: str) -> str:
    return f'[project]\nname = "grasp"\nversion = "{version}"\n'


def init(version: str) -> str:
    return f'__version__ = "{version}"\n'


def history(*versions: str, current: str | None = None, package: str | None = None) -> str:
    current_version = current or versions[0]
    package_version = package or versions[0]
    entries = "\n".join(
        f"- `{version}`（更新: 2026-06-28 00:00、store: schema `8`, compat: schema `8` compatible）: entry"
        for version in versions
    )
    return (
        "## Version history\n\n"
        f"{entries}\n\n"
        "## Current state\n\n"
        f"- Current public compatibility version: `{current_version}`\n"
        "- Current internal `SCHEMA_VERSION`: `8`\n"
        f"- Current package metadata should match `{package_version}`; pre-policy `0.1.0` は release compatibility を表す番号として使わない。\n"
    )


def implemented(version: str) -> str:
    return f"## store\n\n- current public compatibility version は `{version}`。release / store compatibility の履歴と bump rule は [[history]]。\n"


class WikiVersionLedgerScriptTests(unittest.TestCase):
    def test_clean_version_ledger_has_no_errors(self):
        self.assertEqual(
            ledger.wiki_version_ledger_errors(
                pyproject_text=pyproject("1.8.58"),
                init_text=init("1.8.58"),
                history_text=history("1.8.58", "1.8.57", "1.8.56"),
                implemented_text=implemented("1.8.58"),
            ),
            [],
        )

    def test_detects_current_facts_drift(self):
        errors = ledger.wiki_version_ledger_errors(
            pyproject_text=pyproject("1.8.58"),
            init_text=init("1.8.58"),
            history_text=history("1.8.58", "1.8.57"),
            implemented_text=implemented("1.8.56"),
        )

        self.assertTrue(any("grasp-v1-implemented current public compatibility version" in error for error in errors))
        self.assertTrue(any("1.8.56" in error for error in errors))

    def test_detects_duplicate_history_versions(self):
        errors = ledger.wiki_version_ledger_errors(
            pyproject_text=pyproject("1.8.58"),
            init_text=init("1.8.58"),
            history_text=history("1.8.58", "1.8.57", "1.8.57"),
            implemented_text=implemented("1.8.58"),
        )

        self.assertTrue(any("duplicate version entries" in error for error in errors))

    def test_detects_history_order_drift(self):
        errors = ledger.wiki_version_ledger_errors(
            pyproject_text=pyproject("1.8.58"),
            init_text=init("1.8.58"),
            history_text=history("1.8.57", "1.8.58", current="1.8.58", package="1.8.58"),
            implemented_text=implemented("1.8.58"),
        )

        self.assertTrue(any("latest entry" in error for error in errors))
        self.assertTrue(any("descending semver order" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
