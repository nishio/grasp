import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RENAME_PARENT = "d4e4c39dbec278897137c9567765fcef3ed0668d^"
RENAME_COMMIT = "d4e4c39dbec278897137c9567765fcef3ed0668d"
OLD_PATH = "decisions/why-design-B.md"
NEW_PATH = "decisions/why-not-scrapbox-clone.md"
NEW_TITLE = "Decision: Scrapbox を忠実 clone せず、identity-without-name を足した「あるべき姿」を作る"
RENAME_EVENT_KEY = f"rename:{OLD_PATH}->{NEW_PATH}"
RENAME_SUPPORT_PATHS = [
    "SPEC.md",
    "index.md",
    "log.md",
    "decisions/persistence-custom-format.md",
]
PAGE_CREATE_COMMIT = "0db144926a27591eb80a72ed1cc3f696dcf96afd"
PLAN_PATH = "llm-wiki-infra-fast-path-plan.md"
PLAN_TITLE = "LLM Wiki infra fast-path plan"
PLAN_CREATE_EVENT_KEY = f"create:{PLAN_PATH}"
PAGE_CREATE_EXISTING_PATHS = [
    "decisions/native-authority-markdown-projection.md",
    "index.md",
    "log.md",
]
STORED_LINE_IDS_COMMIT = "a07f1afb9af88bce6e47592f01a1425e0765e6c5"
STORED_LINE_IDS_PATHS = [
    "entities/grasp-v1-implemented.md",
    "grasp-backlog.md",
    "history.md",
    PLAN_PATH,
    "log.md",
]
SOURCE_DIGEST_POLICY_COMMIT = "3eaab7516378dde8c26e75329fda7edca49558db"
SOURCE_DIGEST_POLICY_PATHS = [
    "decisions/markdown-identity-name-collision-policy.md",
    "decisions/markdown-obsidian-indexed-mirror.md",
    "entities/wiki-forest-markdown-import-dogfood-2026-06-25.md",
    "grasp-backlog.md",
    "index.md",
    "log.md",
]
SOURCE_DIGEST_POLICY_BACKLOG_UPDATE_EVENT_KEY = (
    f"update:{SOURCE_DIGEST_POLICY_COMMIT}:grasp-backlog.md"
)
SOURCE_ROLE_COMMIT = "3605e05005e227cf525255b5cd3b70c3349c71e4"
SOURCE_ROLE_PATHS = [
    "decisions/markdown-identity-name-collision-policy.md",
    "decisions/markdown-obsidian-indexed-mirror.md",
    "entities/grasp-v1-implemented.md",
    "entities/wiki-forest-markdown-import-dogfood-2026-06-25.md",
    "grasp-backlog.md",
    "history.md",
    "index.md",
    "log.md",
]
HANDLE_BINDING_COMMIT = "7360053e07a161da8a528746b078de87dcecfb03"
HANDLE_BINDING_PATHS = [
    "decisions/markdown-identity-name-collision-policy.md",
    "entities/grasp-v1-implemented.md",
    "entities/wiki-forest-markdown-import-dogfood-2026-06-25.md",
    "grasp-backlog.md",
    "history.md",
    "index.md",
    "log.md",
]
EDGE_RESOLUTION_COMMIT = "827806943765365c4511d75fbf7316590c269f47"
EDGE_RESOLUTION_PATHS = [
    "decisions/markdown-identity-name-collision-policy.md",
    "decisions/markdown-obsidian-indexed-mirror.md",
    "entities/grasp-v1-implemented.md",
    "entities/wiki-forest-markdown-import-dogfood-2026-06-25.md",
    "grasp-backlog.md",
    "history.md",
    "index.md",
    "log.md",
]
SQLITE_SSOT_PLAN_COMMIT = "b6442374663b49a197b14bc60c27cef8c841fcfc"
SQLITE_SSOT_PLAN_PATH = "sqlite-ssot-write-plan.md"
SQLITE_SSOT_PLAN_TITLE = "SQLite SSoT write plan"
SQLITE_SSOT_PLAN_EXISTING_PATHS = [
    "grasp-backlog.md",
    "index.md",
    "llm-wiki-infra-fast-path-plan.md",
    "log.md",
]
SQLITE_SSOT_PLAN_PATHS = [
    *SQLITE_SSOT_PLAN_EXISTING_PATHS,
    SQLITE_SSOT_PLAN_PATH,
]
INFERRED_PLAN_DEPENDENTS_COMMIT = "5f1b82161e16c7ee813ee34ee7a2636215119515"
INFERRED_PLAN_DEPENDENTS_PATHS = [
    "entities/grasp-v1-implemented.md",
    "grasp-backlog.md",
    "history.md",
    "sqlite-ssot-write-plan.md",
    "log.md",
]
CONTINUOUS_REPLAY_SEQUENCES = [
    {
        "name": "rename-then-revert-design-decision",
        "support_paths": RENAME_SUPPORT_PATHS,
        "steps": [
            {
                "commit": RENAME_COMMIT,
                "rename_pages": [
                    {
                        "old_path": OLD_PATH,
                        "new_path": NEW_PATH,
                        "new_title": NEW_TITLE,
                    }
                ],
                "revert_events": [
                    {
                        "event_key": RENAME_EVENT_KEY,
                        "target_event_type": "page_rename",
                    }
                ],
            },
        ],
        "read_handle": "why-design-B",
        "expected_title": "Decision: design B — 単一 AI 所有の Scrapbox 型グラフストア",
        "assert_path": OLD_PATH,
        "assert_text": "# Decision: design B",
        "absent_paths": [NEW_PATH],
        "exact_projection_paths": [*RENAME_SUPPORT_PATHS, OLD_PATH],
        "final_revision": RENAME_PARENT,
    },
    {
        "name": "create-then-revert-fast-path-plan",
        "steps": [
            {
                "commit": PAGE_CREATE_COMMIT,
                "create_pages": [(PLAN_PATH, PLAN_TITLE)],
                "update_paths": PAGE_CREATE_EXISTING_PATHS,
                "revert_events": [
                    {
                        "event_key": PLAN_CREATE_EVENT_KEY,
                        "target_event_type": "page_create",
                    }
                ],
            },
        ],
        "read_handle": "native-authority-markdown-projection",
        "expected_title": "Decision: native authority + Markdown projection で LLM Wiki を移行する",
        "assert_path": "log.md",
        "assert_text": "LLM Wiki infra fast-path plan",
        "absent_paths": [PLAN_PATH],
        "exact_projection_paths": PAGE_CREATE_EXISTING_PATHS,
    },
    {
        "name": "rename-design-decision",
        "support_paths": RENAME_SUPPORT_PATHS,
        "steps": [
            {
                "commit": RENAME_COMMIT,
                "rename_pages": [
                    {
                        "old_path": OLD_PATH,
                        "new_path": NEW_PATH,
                        "new_title": NEW_TITLE,
                    }
                ],
            },
        ],
        "read_handle": "why-design-B",
        "expected_title": NEW_TITLE,
        "assert_path": NEW_PATH,
        "assert_text": "  - why-design-B",
        "absent_paths": [OLD_PATH],
        "exact_projection_paths": [],
    },
    {
        "name": "create-then-update-fast-path-plan",
        "steps": [
            {
                "commit": PAGE_CREATE_COMMIT,
                "create_pages": [(PLAN_PATH, PLAN_TITLE)],
                "update_paths": PAGE_CREATE_EXISTING_PATHS,
            },
            {
                "commit": STORED_LINE_IDS_COMMIT,
                "update_paths": STORED_LINE_IDS_PATHS,
            },
        ],
        "read_handle": "llm-wiki-infra-fast-path-plan",
        "expected_title": PLAN_TITLE,
        "assert_path": PLAN_PATH,
        "assert_text": "authoring dogfood loop",
    },
    {
        "name": "source-role",
        "steps": [
            {"commit": SOURCE_DIGEST_POLICY_COMMIT, "update_paths": SOURCE_DIGEST_POLICY_PATHS},
            {"commit": SOURCE_ROLE_COMMIT, "update_paths": SOURCE_ROLE_PATHS},
        ],
        "read_handle": "grasp-v1-implemented",
        "expected_title": "entity: grasp v1 implemented surface",
        "assert_path": "entities/grasp-v1-implemented.md",
        "assert_text": "`source/` / `sources/`",
    },
    {
        "name": "multi-page-update-then-revert-one-page",
        "steps": [
            {
                "commit": SOURCE_DIGEST_POLICY_COMMIT,
                "update_paths": SOURCE_DIGEST_POLICY_PATHS,
                "revert_events": [
                    {
                        "event_key": SOURCE_DIGEST_POLICY_BACKLOG_UPDATE_EVENT_KEY,
                        "target_event_type": "page_update",
                    }
                ],
            },
        ],
        "read_handle": "grasp-backlog",
        "expected_title": "grasp backlog",
        "assert_path": "grasp-backlog.md",
        "assert_text": "`drafts/` / `source/` artifact 除外",
        "exact_projection_paths": SOURCE_DIGEST_POLICY_PATHS,
        "final_path_revisions": {
            "grasp-backlog.md": f"{SOURCE_DIGEST_POLICY_COMMIT}^",
        },
    },
    {
        "name": "handle-ambiguity",
        "steps": [
            {"commit": HANDLE_BINDING_COMMIT, "update_paths": HANDLE_BINDING_PATHS},
            {"commit": EDGE_RESOLUTION_COMMIT, "update_paths": EDGE_RESOLUTION_PATHS},
        ],
        "read_handle": "grasp-v1-implemented",
        "expected_title": "entity: grasp v1 implemented surface",
        "assert_path": "decisions/markdown-identity-name-collision-policy.md",
        "assert_text": "resolution_status=ambiguous",
    },
]
HISTORY_FIXTURE_PATHS = [
    "SPEC.md",
    "index.md",
    "log.md",
    "decisions/persistence-custom-format.md",
    OLD_PATH,
]


def git_show_file(revision: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{revision}:wiki/{path}"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def git_show_files(revision: str, paths: list[str]) -> dict[str, str]:
    return {path: git_show_file(revision, path) for path in paths}


def replay_step_paths(step: dict) -> list[str]:
    create_paths = [path for path, _ in step.get("create_pages", [])]
    rename_paths = [rename["new_path"] for rename in step.get("rename_pages", [])]
    return [*create_paths, *rename_paths, *step.get("update_paths", [])]


def replay_sequence_paths(sequence: dict) -> list[str]:
    return list(dict.fromkeys(path for step in sequence["steps"] for path in replay_step_paths(step)))


def replay_sequence_create_paths(sequence: dict) -> set[str]:
    return {
        path
        for step in sequence["steps"]
        for path, _ in step.get("create_pages", [])
    }


def replay_sequence_rename_old_paths(sequence: dict) -> list[str]:
    return [
        rename["old_path"]
        for step in sequence["steps"]
        for rename in step.get("rename_pages", [])
    ]


def replay_sequence_rename_new_paths(sequence: dict) -> set[str]:
    return {
        rename["new_path"]
        for step in sequence["steps"]
        for rename in step.get("rename_pages", [])
    }


def replay_sequence_initial_paths(sequence: dict) -> list[str]:
    create_paths = replay_sequence_create_paths(sequence)
    rename_new_paths = replay_sequence_rename_new_paths(sequence)
    return list(
        dict.fromkeys(
            [
                *sequence.get("support_paths", []),
                *replay_sequence_rename_old_paths(sequence),
                *(
                    path
                    for path in replay_sequence_paths(sequence)
                    if path not in create_paths and path not in rename_new_paths
                ),
            ]
        )
    )


def replay_sequence_projection_read_paths(sequence: dict, exact_projection_paths: list[str]) -> list[str]:
    return list(dict.fromkeys([*exact_projection_paths, sequence["assert_path"]]))


def write_fixture_files(root: Path, fixture: dict[str, str]) -> None:
    for relative_path, text in fixture.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def replay_sequence_final_fixture(
    sequence: dict,
    final_revision: str,
    exact_projection_paths: list[str],
) -> dict[str, str]:
    path_revisions = sequence.get("final_path_revisions", {})
    return {
        path: git_show_file(path_revisions.get(path, final_revision), path)
        for path in exact_projection_paths
    }


def run_grasp_json(*args: str | Path) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "grasp", "--json", *(str(arg) for arg in args)],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


@unittest.skipUnless((REPO_ROOT / ".git").exists(), "git history fixture requires a git checkout")
class GitHistoryReplayTests(unittest.TestCase):
    def test_actual_wiki_rename_keeps_old_surface_links_without_redirect_stub(self):
        try:
            fixture = {path: git_show_file(RENAME_PARENT, path) for path in HISTORY_FIXTURE_PATHS}
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            for relative_path, text in fixture.items():
                target = root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")

            store_path = Path(tmpdir) / "store.sqlite"
            reimport_store_path = Path(tmpdir) / "reimport.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            rename_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "rename-page",
                    "--target",
                    "path",
                    OLD_PATH,
                    NEW_TITLE,
                    "--new-path",
                    NEW_PATH,
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            rename_result = json.loads(rename_completed.stdout)
            read_old_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "why-design-B",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            reimport_old_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "--project",
                    "wiki",
                    "read",
                    "why-design-B",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            projection_text = (root / NEW_PATH).read_text(encoding="utf-8")
            log_text = (root / "log.md").read_text(encoding="utf-8")
            old_stub_exists = (root / OLD_PATH).exists()

        read_old = json.loads(read_old_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        reimport_old = json.loads(reimport_old_completed.stdout)
        self.assertFalse(old_stub_exists)
        self.assertEqual(rename_result["previous_source_path"], OLD_PATH)
        self.assertEqual(rename_result["source_path"], NEW_PATH)
        self.assertEqual(read_old["page"]["id"], rename_result["page"]["id"])
        self.assertEqual(read_old["page"]["title"], NEW_TITLE)
        self.assertGreaterEqual(read_old["backlink_count_total"], 3)
        self.assertTrue(replay_result["ok"])
        self.assertEqual(reimport_old["page"]["id"], rename_result["page"]["id"])
        self.assertEqual(reimport_old["page"]["title"], NEW_TITLE)
        self.assertGreaterEqual(reimport_old["backlink_count_total"], 3)
        self.assertIn("id: " + rename_result["page"]["id"], projection_text)
        self.assertIn("  - why-design-B", projection_text)
        self.assertIn("[[why-design-B]]", log_text)

    def test_actual_wiki_page_create_and_updates_replay_cleanly(self):
        try:
            before_fixture = {
                path: git_show_file(f"{PAGE_CREATE_COMMIT}^", path)
                for path in PAGE_CREATE_EXISTING_PATHS
            }
            after_fixture = {
                path: git_show_file(PAGE_CREATE_COMMIT, path)
                for path in [*PAGE_CREATE_EXISTING_PATHS, PLAN_PATH]
            }
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            after_root = Path(tmpdir) / "after"
            after_root.mkdir()
            for relative_path, text in before_fixture.items():
                target = root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            for relative_path, text in after_fixture.items():
                target = after_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")

            store_path = Path(tmpdir) / "store.sqlite"
            reimport_store_path = Path(tmpdir) / "reimport.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            create_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "write-page",
                    PLAN_TITLE,
                    "--create",
                    "--path",
                    PLAN_PATH,
                    "--from-file",
                    str(after_root / PLAN_PATH),
                    "--output",
                    str(root),
                    "--journal",
                    str(journal_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            for target, relative_path in [
                ("native-authority-markdown-projection", "decisions/native-authority-markdown-projection.md"),
                ("index", "index.md"),
                ("log", "log.md"),
            ]:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        "write-page",
                        target,
                        "--from-file",
                        str(after_root / relative_path),
                        "--output",
                        str(root),
                        "--journal",
                        str(journal_path),
                    ],
                    cwd=REPO_ROOT,
                    check=True,
                    text=True,
                    capture_output=True,
                )

            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            reimport_plan_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "--project",
                    "wiki",
                    "read",
                    "llm-wiki-infra-fast-path-plan",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            projected_texts = {
                path: (root / path).read_text(encoding="utf-8")
                for path in after_fixture
            }

        create_result = json.loads(create_completed.stdout)
        replay_result = json.loads(replay_completed.stdout)
        reimport_plan = json.loads(reimport_plan_completed.stdout)
        projection_event_types = [
            event["event_type"]
            for event in journal_events
            if event["event_type"] != "log_entry_import"
        ]
        log_entry_events = [
            event
            for event in journal_events
            if event["event_type"] == "log_entry_import"
        ]
        self.assertEqual(
            projection_event_types,
            [
                "page_create",
                "page_create",
                "page_create",
                "page_create",
                "page_update",
                "page_update",
                "page_update",
            ],
        )
        self.assertGreater(len(log_entry_events), 0)
        self.assertTrue(
            all(event["payload"]["source_path"] == "log.md" for event in log_entry_events)
        )
        self.assertEqual(create_result["event_type"], "page_create")
        self.assertEqual(create_result["source_path"], PLAN_PATH)
        self.assertEqual(create_result["page"]["title"], PLAN_TITLE)
        self.assertGreater(create_result["edge_count"], 0)
        self.assertTrue(replay_result["ok"])
        self.assertEqual(projected_texts, after_fixture)
        self.assertEqual(reimport_plan["page"]["title"], PLAN_TITLE)
        self.assertGreaterEqual(reimport_plan["backlink_count_total"], 1)

    def test_actual_source_digest_policy_multi_page_update_replays_cleanly(self):
        try:
            before_fixture = {
                path: git_show_file(f"{SOURCE_DIGEST_POLICY_COMMIT}^", path)
                for path in SOURCE_DIGEST_POLICY_PATHS
            }
            after_fixture = {
                path: git_show_file(SOURCE_DIGEST_POLICY_COMMIT, path)
                for path in SOURCE_DIGEST_POLICY_PATHS
            }
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            after_root = Path(tmpdir) / "after"
            after_root.mkdir()
            for relative_path, text in before_fixture.items():
                target = root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            for relative_path, text in after_fixture.items():
                target = after_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")

            store_path = Path(tmpdir) / "store.sqlite"
            reimport_store_path = Path(tmpdir) / "reimport.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "adopt-markdown",
                    str(root),
                    "--project",
                    "wiki",
                    "--journal",
                    str(journal_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            update_results = []
            for relative_path in SOURCE_DIGEST_POLICY_PATHS:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        "write-page",
                        Path(relative_path).stem,
                        "--from-file",
                        str(after_root / relative_path),
                        "--output",
                        str(root),
                        "--journal",
                        str(journal_path),
                    ],
                    cwd=REPO_ROOT,
                    check=True,
                    text=True,
                    capture_output=True,
                )
                update_results.append(json.loads(completed.stdout))

            replay_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--project",
                    "wiki",
                    "replay-journal",
                    "--journal",
                    str(journal_path),
                    "--output",
                    str(root),
                    "--check",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "import",
                    "--markdown",
                    str(root),
                    "--project",
                    "wiki",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            reimport_source_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(reimport_store_path),
                    "--project",
                    "wiki",
                    "read",
                    "wiki-forest-markdown-import-dogfood-2026-06-25",
                    "--related-limit",
                    "0",
                    "--unresolved-limit",
                    "0",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            projected_texts = {
                path: (root / path).read_text(encoding="utf-8")
                for path in SOURCE_DIGEST_POLICY_PATHS
            }

        replay_result = json.loads(replay_completed.stdout)
        reimport_source = json.loads(reimport_source_completed.stdout)
        projection_event_types = [
            event["event_type"]
            for event in journal_events
            if event["event_type"] != "log_entry_import"
        ]
        self.assertEqual(
            projection_event_types,
            ["page_create"] * len(SOURCE_DIGEST_POLICY_PATHS)
            + ["page_update"] * len(SOURCE_DIGEST_POLICY_PATHS),
        )
        self.assertEqual(
            [result["source_path"] for result in update_results],
            SOURCE_DIGEST_POLICY_PATHS,
        )
        self.assertTrue(all(result["event_type"] == "page_update" for result in update_results))
        self.assertTrue(replay_result["ok"])
        self.assertEqual(projected_texts, after_fixture)
        self.assertEqual(
            reimport_source["page"]["title"],
            "wiki森 Markdown import dogfood 2026-06-25",
        )
        self.assertIn(
            "`source/` は `raw/` と同列に扱わない",
            projected_texts["entities/wiki-forest-markdown-import-dogfood-2026-06-25.md"],
        )

    def test_revert_plan_log_page_subjects_uses_direct_log_update_in_git_history(self):
        try:
            before_fixture = {
                path: git_show_file(f"{SOURCE_DIGEST_POLICY_COMMIT}^", path)
                for path in SOURCE_DIGEST_POLICY_PATHS
            }
            after_fixture = {
                path: git_show_file(SOURCE_DIGEST_POLICY_COMMIT, path)
                for path in SOURCE_DIGEST_POLICY_PATHS
            }
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            after_root = Path(tmpdir) / "after"
            after_root.mkdir()
            write_fixture_files(root, before_fixture)
            write_fixture_files(after_root, after_fixture)
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            run_grasp_json(
                "--store",
                store_path,
                "adopt-markdown",
                root,
                "--project",
                "wiki",
                "--journal",
                journal_path,
            )
            update_results_by_path = {}
            for relative_path in SOURCE_DIGEST_POLICY_PATHS:
                update_results_by_path[relative_path] = run_grasp_json(
                    "--store",
                    store_path,
                    "--project",
                    "wiki",
                    "write-page",
                    Path(relative_path).stem,
                    "--from-file",
                    after_root / relative_path,
                    "--output",
                    root,
                    "--journal",
                    journal_path,
                )

            anchor_event_id = update_results_by_path[
                "entities/wiki-forest-markdown-import-dogfood-2026-06-25.md"
            ]["event_id"]
            plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "log-page-subjects",
                "--output",
                root,
            )
            subject_log_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "subject-log",
                "--output",
                root,
            )
            index_anchor_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                update_results_by_path["index.md"]["event_id"],
                "--scope",
                "log-page-subjects",
                "--output",
                root,
            )
            projected_texts_after_plan = {
                path: (root / path).read_text(encoding="utf-8")
                for path in SOURCE_DIGEST_POLICY_PATHS
            }

        expected_candidate_paths = [
            "decisions/markdown-identity-name-collision-policy.md",
            "decisions/markdown-obsidian-indexed-mirror.md",
            "entities/wiki-forest-markdown-import-dogfood-2026-06-25.md",
            "grasp-backlog.md",
            "log.md",
        ]
        self.assertFalse(subject_log_plan["complete"])
        self.assertIn("no closing log_append", subject_log_plan["reason"])
        self.assertEqual(plan["scope"], "log-page-subjects")
        self.assertTrue(plan["complete"])
        self.assertTrue(plan["revertible"])
        self.assertEqual(plan["closing_log_event"]["event_id"], update_results_by_path["log.md"]["event_id"])
        self.assertEqual(
            plan["log_page_subjects"],
            [
                "wiki-forest-markdown-import-dogfood-2026-06-25",
                "grasp-backlog",
                "markdown-identity-name-collision-policy",
                "markdown-obsidian-indexed-mirror",
            ],
        )
        self.assertEqual(
            plan["candidate_event_ids"],
            [update_results_by_path[path]["event_id"] for path in expected_candidate_paths],
        )
        self.assertEqual(
            plan["revert_order_event_ids"],
            [update_results_by_path[path]["event_id"] for path in reversed(expected_candidate_paths)],
        )
        self.assertEqual(
            [event["source_path"] for event in plan["candidate_events"]],
            expected_candidate_paths,
        )
        self.assertEqual(
            [event["source_path"] for event in plan["excluded_events"]],
            ["index.md"],
        )
        self.assertIn("does not match closing log page subjects", plan["excluded_events"][0]["reason"])
        self.assertEqual(
            [event["target_event_id"] for event in plan["reverted_events"]],
            [update_results_by_path[path]["event_id"] for path in reversed(expected_candidate_paths)],
        )
        self.assertEqual(
            plan["suggested_revert_events_args"],
            [
                "revert-events",
                *[update_results_by_path[path]["event_id"] for path in expected_candidate_paths],
                "--output",
                str(root),
            ],
        )
        self.assertFalse(index_anchor_plan["complete"])
        self.assertFalse(index_anchor_plan["revertible"])
        self.assertIn("does not match closing log page subjects", index_anchor_plan["reason"])
        self.assertEqual(projected_texts_after_plan, after_fixture)

    def test_revert_plan_content_subjects_uses_changed_page_subjects_in_git_history(self):
        try:
            before_fixture = {
                path: git_show_file(f"{SQLITE_SSOT_PLAN_COMMIT}^", path)
                for path in SQLITE_SSOT_PLAN_EXISTING_PATHS
            }
            after_fixture = {
                path: git_show_file(SQLITE_SSOT_PLAN_COMMIT, path)
                for path in SQLITE_SSOT_PLAN_PATHS
            }
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            after_root = Path(tmpdir) / "after"
            after_root.mkdir()
            write_fixture_files(root, before_fixture)
            write_fixture_files(after_root, after_fixture)
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            run_grasp_json(
                "--store",
                store_path,
                "adopt-markdown",
                root,
                "--project",
                "wiki",
                "--journal",
                journal_path,
            )
            update_results_by_path = {}
            update_results_by_path[SQLITE_SSOT_PLAN_PATH] = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "write-page",
                SQLITE_SSOT_PLAN_TITLE,
                "--create",
                "--path",
                SQLITE_SSOT_PLAN_PATH,
                "--from-file",
                after_root / SQLITE_SSOT_PLAN_PATH,
                "--output",
                root,
                "--journal",
                journal_path,
            )
            update_results_by_path["grasp-backlog.md"] = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "write-page",
                "grasp-backlog",
                "--from-file",
                after_root / "grasp-backlog.md",
                "--output",
                root,
                "--journal",
                journal_path,
            )
            for relative_path in [
                path
                for path in SQLITE_SSOT_PLAN_EXISTING_PATHS
                if path != "grasp-backlog.md"
            ]:
                update_results_by_path[relative_path] = run_grasp_json(
                    "--store",
                    store_path,
                    "--project",
                    "wiki",
                    "write-page",
                    Path(relative_path).stem,
                    "--from-file",
                    after_root / relative_path,
                    "--output",
                    root,
                    "--journal",
                    journal_path,
                )

            anchor_event_id = update_results_by_path["grasp-backlog.md"]["event_id"]
            content_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "content-subjects",
                "--output",
                root,
            )
            log_page_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "log-page-subjects",
                "--output",
                root,
            )
            projected_texts_after_plan = {
                path: (root / path).read_text(encoding="utf-8")
                for path in SQLITE_SSOT_PLAN_PATHS
            }

        expected_candidate_paths = [
            SQLITE_SSOT_PLAN_PATH,
            "grasp-backlog.md",
            "index.md",
            "llm-wiki-infra-fast-path-plan.md",
            "log.md",
        ]
        self.assertEqual(content_plan["scope"], "content-subjects")
        self.assertTrue(content_plan["complete"])
        self.assertTrue(content_plan["revertible"])
        self.assertIn("sqlite-ssot-write-plan", content_plan["content_subject_norms"])
        self.assertIn("llm-wiki-infra-fast-path-plan", content_plan["content_subject_norms"])
        self.assertEqual(
            content_plan["candidate_event_ids"],
            [update_results_by_path[path]["event_id"] for path in expected_candidate_paths],
        )
        self.assertEqual(
            [event["source_path"] for event in content_plan["candidate_events"]],
            expected_candidate_paths,
        )
        self.assertEqual(
            content_plan["revert_order_event_ids"],
            [update_results_by_path[path]["event_id"] for path in reversed(expected_candidate_paths)],
        )
        self.assertNotIn(update_results_by_path["index.md"]["event_id"], log_page_plan["candidate_event_ids"])
        self.assertIn(update_results_by_path["index.md"]["event_id"], content_plan["candidate_event_ids"])
        self.assertEqual(projected_texts_after_plan, after_fixture)

    def test_revert_plan_version_bump_uses_shared_semver_in_git_history(self):
        try:
            before_fixture = {
                path: git_show_file(f"{INFERRED_PLAN_DEPENDENTS_COMMIT}^", path)
                for path in INFERRED_PLAN_DEPENDENTS_PATHS
            }
            after_fixture = {
                path: git_show_file(INFERRED_PLAN_DEPENDENTS_COMMIT, path)
                for path in INFERRED_PLAN_DEPENDENTS_PATHS
            }
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            after_root = Path(tmpdir) / "after"
            after_root.mkdir()
            write_fixture_files(root, before_fixture)
            write_fixture_files(after_root, after_fixture)
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

            run_grasp_json(
                "--store",
                store_path,
                "adopt-markdown",
                root,
                "--project",
                "wiki",
                "--journal",
                journal_path,
            )
            update_results_by_path = {}
            for relative_path in INFERRED_PLAN_DEPENDENTS_PATHS:
                update_results_by_path[relative_path] = run_grasp_json(
                    "--store",
                    store_path,
                    "--project",
                    "wiki",
                    "write-page",
                    Path(relative_path).stem,
                    "--from-file",
                    after_root / relative_path,
                    "--output",
                    root,
                    "--journal",
                    journal_path,
                )

            anchor_event_id = update_results_by_path["history.md"]["event_id"]
            version_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "version-bump",
                "--output",
                root,
            )
            content_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "content-subjects",
                "--output",
                root,
            )
            log_page_plan = run_grasp_json(
                "--store",
                store_path,
                "--project",
                "wiki",
                "revert-plan",
                anchor_event_id,
                "--scope",
                "log-page-subjects",
                "--output",
                root,
            )
            projected_texts_after_plan = {
                path: (root / path).read_text(encoding="utf-8")
                for path in INFERRED_PLAN_DEPENDENTS_PATHS
            }

        self.assertEqual(version_plan["scope"], "version-bump")
        self.assertTrue(version_plan["complete"])
        self.assertTrue(version_plan["revertible"])
        self.assertEqual(version_plan["version_bump_versions"], ["1.8.37"])
        self.assertEqual(
            version_plan["candidate_event_ids"],
            [update_results_by_path[path]["event_id"] for path in INFERRED_PLAN_DEPENDENTS_PATHS],
        )
        self.assertEqual(
            [event["source_path"] for event in version_plan["candidate_events"]],
            INFERRED_PLAN_DEPENDENTS_PATHS,
        )
        self.assertEqual(
            version_plan["revert_order_event_ids"],
            [update_results_by_path[path]["event_id"] for path in reversed(INFERRED_PLAN_DEPENDENTS_PATHS)],
        )
        self.assertNotEqual(content_plan["candidate_event_ids"], version_plan["candidate_event_ids"])
        self.assertFalse(log_page_plan["complete"])
        self.assertIn("no newly added wikilink or Markdown path subjects", log_page_plan["reason"])
        self.assertEqual(projected_texts_after_plan, after_fixture)

    def test_actual_consecutive_wiki_history_replay_cleanly(self):
        for sequence in CONTINUOUS_REPLAY_SEQUENCES:
            with self.subTest(sequence=sequence["name"]):
                steps = sequence["steps"]
                sequence_paths = replay_sequence_paths(sequence)
                initial_paths = replay_sequence_initial_paths(sequence)
                try:
                    before_fixture = git_show_files(f"{steps[0]['commit']}^", initial_paths)
                    step_fixtures = [
                        (step, git_show_files(step["commit"], replay_step_paths(step)))
                        for step in steps
                    ]
                    exact_projection_paths = sequence.get("exact_projection_paths", sequence_paths)
                    final_revision = sequence.get("final_revision", steps[-1]["commit"])
                    final_fixture = replay_sequence_final_fixture(
                        sequence,
                        final_revision,
                        exact_projection_paths,
                    )
                except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                    raise unittest.SkipTest(f"git history fixture unavailable: {exc}") from exc

                with tempfile.TemporaryDirectory() as tmpdir:
                    root = Path(tmpdir) / "wiki"
                    root.mkdir()
                    write_fixture_files(root, before_fixture)
                    store_path = Path(tmpdir) / "store.sqlite"
                    reimport_store_path = Path(tmpdir) / "reimport.sqlite"
                    journal_path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"

                    run_grasp_json(
                        "--store",
                        store_path,
                        "adopt-markdown",
                        root,
                        "--project",
                        "wiki",
                        "--journal",
                        journal_path,
                    )
                    created_source_paths_by_commit = []
                    renamed_source_paths_by_commit = []
                    update_source_paths_by_commit = []
                    reverted_event_keys_by_commit = []
                    event_ids_by_key = {}
                    replay_results = []
                    for step, fixture in step_fixtures:
                        commit = step["commit"]
                        step_root = Path(tmpdir) / commit[:7]
                        step_root.mkdir()
                        write_fixture_files(step_root, fixture)
                        commit_created_paths = []
                        for relative_path, title in step.get("create_pages", []):
                            result = run_grasp_json(
                                "--store",
                                store_path,
                                "--project",
                                "wiki",
                                "write-page",
                                title,
                                "--create",
                                "--path",
                                relative_path,
                                "--from-file",
                                step_root / relative_path,
                                "--output",
                                root,
                                "--journal",
                                journal_path,
                            )
                            self.assertEqual(result["event_type"], "page_create")
                            commit_created_paths.append(result["source_path"])
                            event_ids_by_key[f"create:{relative_path}"] = result["event_id"]
                        created_source_paths_by_commit.append(commit_created_paths)
                        commit_renamed_paths = []
                        for rename in step.get("rename_pages", []):
                            result = run_grasp_json(
                                "--store",
                                store_path,
                                "--project",
                                "wiki",
                                "rename-page",
                                "--target",
                                "path",
                                rename["old_path"],
                                rename["new_title"],
                                "--new-path",
                                rename["new_path"],
                                "--output",
                                root,
                                "--journal",
                                journal_path,
                            )
                            self.assertEqual(result["event_type"], "page_rename")
                            commit_renamed_paths.append(
                                (result["previous_source_path"], result["source_path"])
                            )
                            event_ids_by_key[
                                f"rename:{rename['old_path']}->{rename['new_path']}"
                            ] = result["event_id"]
                        renamed_source_paths_by_commit.append(commit_renamed_paths)
                        commit_source_paths = []
                        for relative_path in step.get("update_paths", []):
                            result = run_grasp_json(
                                "--store",
                                store_path,
                                "--project",
                                "wiki",
                                "write-page",
                                Path(relative_path).stem,
                                "--from-file",
                                step_root / relative_path,
                                "--output",
                                root,
                                "--journal",
                                journal_path,
                            )
                            self.assertEqual(result["event_type"], "page_update")
                            commit_source_paths.append(result["source_path"])
                            event_ids_by_key[f"update:{commit}:{relative_path}"] = result["event_id"]
                        update_source_paths_by_commit.append(commit_source_paths)
                        commit_reverted_event_keys = []
                        for revert in step.get("revert_events", []):
                            target_event_id = event_ids_by_key[revert["event_key"]]
                            result = run_grasp_json(
                                "--store",
                                store_path,
                                "--project",
                                "wiki",
                                "revert-event",
                                target_event_id,
                                "--output",
                                root,
                                "--journal",
                                journal_path,
                            )
                            self.assertEqual(result["target_event_type"], revert["target_event_type"])
                            commit_reverted_event_keys.append(revert["event_key"])
                        reverted_event_keys_by_commit.append(commit_reverted_event_keys)
                        replay_results.append(
                            run_grasp_json(
                                "--project",
                                "wiki",
                                "replay-journal",
                                "--journal",
                                journal_path,
                                "--output",
                                root,
                                "--check",
                            )
                        )

                    run_grasp_json(
                        "--store",
                        reimport_store_path,
                        "import",
                        "--markdown",
                        root,
                        "--project",
                        "wiki",
                    )
                    reimport_read = run_grasp_json(
                        "--store",
                        reimport_store_path,
                        "--project",
                        "wiki",
                        "read",
                        sequence["read_handle"],
                        "--related-limit",
                        "0",
                        "--unresolved-limit",
                        "0",
                    )
                    journal_events = [
                        json.loads(line)
                        for line in journal_path.read_text(encoding="utf-8").splitlines()
                    ]
                    projection_read_paths = replay_sequence_projection_read_paths(
                        sequence,
                        exact_projection_paths,
                    )
                    exact_projected_texts = {
                        path: (root / path).read_text(encoding="utf-8")
                        for path in exact_projection_paths
                    }
                    projected_texts = {
                        path: (root / path).read_text(encoding="utf-8")
                        for path in projection_read_paths
                    }
                    absent_path_exists = {
                        path: (root / path).exists()
                        for path in sequence.get("absent_paths", [])
                    }

                projection_event_types = [
                    event["event_type"]
                    for event in journal_events
                    if event["event_type"] != "log_entry_import"
                ]
                expected_projection_event_types = ["page_create"] * len(initial_paths)
                for step in steps:
                    expected_projection_event_types.extend(
                        ["page_create"] * len(step.get("create_pages", []))
                    )
                    expected_projection_event_types.extend(
                        ["page_rename"] * len(step.get("rename_pages", []))
                    )
                    expected_projection_event_types.extend(
                        ["page_update"] * len(step.get("update_paths", []))
                    )
                    expected_projection_event_types.extend(
                        ["event_revert"] * len(step.get("revert_events", []))
                    )
                self.assertEqual(
                    projection_event_types,
                    expected_projection_event_types,
                )
                self.assertEqual(
                    created_source_paths_by_commit,
                    [
                        [path for path, _ in step.get("create_pages", [])]
                        for step in steps
                    ],
                )
                self.assertEqual(
                    renamed_source_paths_by_commit,
                    [
                        [
                            (rename["old_path"], rename["new_path"])
                            for rename in step.get("rename_pages", [])
                        ]
                        for step in steps
                    ],
                )
                self.assertEqual(
                    update_source_paths_by_commit,
                    [step.get("update_paths", []) for step in steps],
                )
                self.assertEqual(
                    reverted_event_keys_by_commit,
                    [
                        [revert["event_key"] for revert in step.get("revert_events", [])]
                        for step in steps
                    ],
                )
                self.assertTrue(all(result["ok"] for result in replay_results))
                self.assertEqual(exact_projected_texts, final_fixture)
                self.assertFalse(any(absent_path_exists.values()))
                self.assertEqual(reimport_read["page"]["title"], sequence["expected_title"])
                self.assertIn(
                    sequence["assert_text"],
                    projected_texts[sequence["assert_path"]],
                )
