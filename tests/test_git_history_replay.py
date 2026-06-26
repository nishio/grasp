import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RENAME_PARENT = "d4e4c39dbec278897137c9567765fcef3ed0668d^"
OLD_PATH = "decisions/why-design-B.md"
NEW_PATH = "decisions/why-not-scrapbox-clone.md"
NEW_TITLE = "Decision: Scrapbox を忠実 clone せず、identity-without-name を足した「あるべき姿」を作る"
PAGE_CREATE_COMMIT = "0db144926a27591eb80a72ed1cc3f696dcf96afd"
PLAN_PATH = "llm-wiki-infra-fast-path-plan.md"
PLAN_TITLE = "LLM Wiki infra fast-path plan"
PAGE_CREATE_EXISTING_PATHS = [
    "decisions/native-authority-markdown-projection.md",
    "index.md",
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
CONTINUOUS_REPLAY_COMMITS = [
    (SOURCE_DIGEST_POLICY_COMMIT, SOURCE_DIGEST_POLICY_PATHS),
    (SOURCE_ROLE_COMMIT, SOURCE_ROLE_PATHS),
]
CONTINUOUS_REPLAY_PATHS = list(
    dict.fromkeys(path for _, paths in CONTINUOUS_REPLAY_COMMITS for path in paths)
)
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


def write_fixture_files(root: Path, fixture: dict[str, str]) -> None:
    for relative_path, text in fixture.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


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

    def test_actual_consecutive_wiki_updates_replay_cleanly(self):
        try:
            before_fixture = git_show_files(f"{SOURCE_DIGEST_POLICY_COMMIT}^", CONTINUOUS_REPLAY_PATHS)
            step_fixtures = [
                (commit, paths, git_show_files(commit, paths))
                for commit, paths in CONTINUOUS_REPLAY_COMMITS
            ]
            final_fixture = git_show_files(SOURCE_ROLE_COMMIT, CONTINUOUS_REPLAY_PATHS)
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
            update_source_paths_by_commit = []
            replay_results = []
            for commit, paths, fixture in step_fixtures:
                step_root = Path(tmpdir) / commit[:7]
                step_root.mkdir()
                write_fixture_files(step_root, fixture)
                commit_source_paths = []
                for relative_path in paths:
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
                update_source_paths_by_commit.append(commit_source_paths)
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
            reimport_implemented = run_grasp_json(
                "--store",
                reimport_store_path,
                "--project",
                "wiki",
                "read",
                "grasp-v1-implemented",
                "--related-limit",
                "0",
                "--unresolved-limit",
                "0",
            )
            journal_events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ]
            projected_texts = {
                path: (root / path).read_text(encoding="utf-8")
                for path in CONTINUOUS_REPLAY_PATHS
            }

        projection_event_types = [
            event["event_type"]
            for event in journal_events
            if event["event_type"] != "log_entry_import"
        ]
        self.assertEqual(
            projection_event_types,
            ["page_create"] * len(CONTINUOUS_REPLAY_PATHS)
            + ["page_update"] * sum(len(paths) for _, paths in CONTINUOUS_REPLAY_COMMITS),
        )
        self.assertEqual(
            update_source_paths_by_commit,
            [paths for _, paths in CONTINUOUS_REPLAY_COMMITS],
        )
        self.assertTrue(all(result["ok"] for result in replay_results))
        self.assertEqual(projected_texts, final_fixture)
        self.assertEqual(
            reimport_implemented["page"]["title"],
            "entity: grasp v1 implemented surface",
        )
        self.assertIn(
            "`source/` / `sources/`",
            projected_texts["entities/grasp-v1-implemented.md"],
        )
