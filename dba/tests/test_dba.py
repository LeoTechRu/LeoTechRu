from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import io
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "lib" / "dba.py"
SPEC = spec_from_file_location("dba_module", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
dba = module_from_spec(SPEC)
sys.modules[SPEC.name] = dba
SPEC.loader.exec_module(dba)

ENTRYPOINT_MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "_entrypoint_common.py"
ENTRYPOINT_SPEC = spec_from_file_location("dba_entrypoint_common", ENTRYPOINT_MODULE_PATH)
assert ENTRYPOINT_SPEC is not None and ENTRYPOINT_SPEC.loader is not None
entrypoints = module_from_spec(ENTRYPOINT_SPEC)
sys.modules[ENTRYPOINT_SPEC.name] = entrypoints
ENTRYPOINT_SPEC.loader.exec_module(entrypoints)


class DBATests(unittest.TestCase):
    def test_entrypoint_confirmation_requires_exact_target(self) -> None:
        with self.assertRaises(entrypoints.WrapperError):
            entrypoints._require_confirmation("wrong", "punkt_b_prod")
        entrypoints._require_confirmation("punkt_b_prod", "punkt_b_prod")

    def test_entrypoint_prints_banner(self) -> None:
        config = entrypoints.EntryPointConfig(
            profile="punktb-prod-ro",
            role="db_readonly_prod",
            database="punkt_b_prod",
            environment="prod",
        )
        with mock.patch("sys.stdout", new_callable=io.StringIO) as fake_stdout:
            entrypoints._print_banner(config, "READONLY")
            text = fake_stdout.getvalue()
        self.assertIn("YOU ARE CONNECTING TO PROD", text)
        self.assertIn("ROLE = db_readonly_prod", text)
        self.assertIn("MODE = READONLY", text)

    def test_parse_env_text_strips_comments(self) -> None:
        values = dba._parse_env_text(
            """
            # comment
            A=1
            B=hello # inline
            C="quoted # keep"
            export D=world
            """
        )
        self.assertEqual(values["A"], "1")
        self.assertEqual(values["B"], "hello")
        self.assertEqual(values["C"], "quoted # keep")
        self.assertEqual(values["D"], "world")

    def test_load_profiles_reads_profile_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DBA_PROFILE__INTDATA_DEV__PGHOST=api.intdata.pro",
                        "DBA_PROFILE__INTDATA_DEV__PGPORT=5432",
                        "DBA_PROFILE__INTDATA_DEV__PGDATABASE=intdata",
                        "DBA_PROFILE__INTDATA_DEV__PGUSER=dev_user",
                        "DBA_PROFILE__INTDATA_DEV__PGPASSWORD=secret",
                        "DBA_PROFILE__INTDATA_DEV__WRITE_CLASS=nonprod",
                    ]
                ),
                encoding="utf-8",
            )
            profile = dba._get_profile(env_path, "intdata-dev")
        self.assertEqual(profile.host, "api.intdata.pro")
        self.assertEqual(profile.port, "5432")
        self.assertEqual(profile.user, "dev_user")
        self.assertEqual(profile.write_class, "nonprod")

    def test_write_guard_requires_exact_approval(self) -> None:
        profile = dba.Profile(
            name="intdata-dev",
            key="INTDATA_DEV",
            values={
                "PGHOST": "api.intdata.pro",
                "PGDATABASE": "intdata",
                "PGUSER": "dev_user",
                "PGPASSWORD": "secret",
            },
        )
        with self.assertRaises(dba.DBAError):
            dba._ensure_write_allowed(profile, approve_target=None, force_prod_write=False)
        dba._ensure_write_allowed(profile, approve_target="intdata-dev", force_prod_write=False)

    def test_prod_guard_requires_force_flag(self) -> None:
        profile = dba.Profile(
            name="intdata-prod",
            key="INTDATA_PROD",
            values={
                "PGHOST": "vds.intdata.pro",
                "PGDATABASE": "intdata",
                "PGUSER": "prod_user",
                "PGPASSWORD": "secret",
                "WRITE_CLASS": "prod",
            },
        )
        with self.assertRaises(dba.DBAError):
            dba._ensure_write_allowed(profile, approve_target="intdata-prod", force_prod_write=False)
        dba._ensure_write_allowed(profile, approve_target="intdata-prod", force_prod_write=True)

    def test_punktb_legacy_target_sql_uses_rollback_for_dry_run(self) -> None:
        sql = dba._build_punktb_legacy_target_sql(
            clients_path=Path("clients.jsonl"),
            managers_path=Path("managers.jsonl"),
            dry_run=True,
        )
        self.assertIn("ROLLBACK;", sql)
        self.assertNotIn("COMMIT;", sql)
        self.assertIn("lower(btrim(raw->>'email'))", sql)
        self.assertIn("pg_temp._dba_uuid('punktb-user-email:' || email_norm)", sql)
        self.assertIn("raw_uuid ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'", sql)
        self.assertIn("'5' || substr(h, 14, 3)", sql)
        self.assertIn("'8' || substr(h, 18, 3)", sql)
        self.assertNotIn("punktb-client-email:", sql)
        self.assertNotIn("punktb-specialist-email:", sql)
        self.assertIn("raw->>'legacy_id'", sql)
        self.assertIn("c.raw->>'legacy_id'", sql)
        self.assertNotIn("legacy-client-", sql)
        self.assertNotIn("legacy-specialist-", sql)
        self.assertIn("target assess.specialists has conflicting legacy numeric slugs", sql)
        self.assertIn("target assess.clients has conflicting legacy numeric slugs", sql)
        self.assertIn("status = assess.specialists.status", sql)
        self.assertIn("'password', password", dba.PUNKTB_LEGACY_MANAGERS_EXPORT_SQL)
        self.assertIn("assess.assess_set_user_password_internal", sql)
        self.assertIn("PUNKTB_PASSWORD_BACKFILL_REQUIRES_ASSESS_SET_USER_PASSWORD_INTERNAL_EXECUTE", sql)
        self.assertIn("WHEN email_norm IN ('leotechru@ya.ru', 'lerida2@ya.ru') THEN email_norm", sql)
        self.assertIn("set_config('request.jwt.claim.role', 'service_role', true)", sql)
        self.assertIn("auth.users", sql)
        self.assertIn("'00000000-0000-0000-0000-000000000000'::uuid", sql)
        self.assertIn("aud = EXCLUDED.aud", sql)
        self.assertIn("instance_id = COALESCE(auth.users.instance_id, EXCLUDED.instance_id)", sql)
        self.assertIn("auth.identities", sql)
        self.assertIn("PUNKTB_AUTH_IDENTITIES_BACKFILL_REQUIRES_AUTH_IDENTITIES_WRITE", sql)
        self.assertIn("'email_verified', true", sql)
        self.assertIn("UNION\n  SELECT email_norm, user_id FROM _dba_punktb_clients", sql)
        self.assertIn("assess.diag_results", sql)

    def test_punktb_legacy_target_sql_uses_commit_for_apply(self) -> None:
        sql = dba._build_punktb_legacy_target_sql(
            clients_path=Path("clients.jsonl"),
            managers_path=Path("managers.jsonl"),
            dry_run=False,
        )
        self.assertIn("COMMIT;", sql)
        self.assertNotIn("ROLLBACK;", sql)

    def test_punktb_export_sql_is_read_only_copy_select(self) -> None:
        self.assertIn("\\copy (", dba.PUNKTB_LEGACY_CLIENTS_EXPORT_SQL)
        self.assertIn("FROM public.clients", dba.PUNKTB_LEGACY_CLIENTS_EXPORT_SQL)
        self.assertNotIn("INSERT", dba.PUNKTB_LEGACY_CLIENTS_EXPORT_SQL.upper())
        self.assertIn("FROM public.managers", dba.PUNKTB_LEGACY_MANAGERS_EXPORT_SQL)
        self.assertNotIn("UPDATE", dba.PUNKTB_LEGACY_MANAGERS_EXPORT_SQL.upper())

    def test_punktb_prod_dev_refresh_target_sql_rolls_back_dry_run(self) -> None:
        sql = dba._build_punktb_prod_dev_refresh_target_sql(Path("dump.sql"), dry_run=True)
        self.assertNotIn("TRUNCATE TABLE", sql)
        self.assertIn("DELETE FROM assess.diag_result_access", sql)
        self.assertIn("DELETE FROM assess.conclusion_results", sql)
        self.assertIn("DELETE FROM assess.conclusions", sql)
        self.assertIn("DELETE FROM assess.diagnostic_assignments", sql)
        self.assertIn("DELETE FROM assess.diag_results;", sql)
        self.assertIn("DELETE FROM assess.clients;", sql)
        self.assertIn("DELETE FROM assess.specialists;", sql)
        self.assertIn("assess.clients", sql)
        self.assertIn("assess.diag_results", sql)
        self.assertNotIn("assess.user_credentials", sql)
        self.assertIn("auth.users", sql)
        self.assertIn("auth.identities", sql)
        self.assertIn("jsonb_populate_record", sql)
        self.assertIn("\\copy _refresh_assess_clients", sql)
        self.assertIn("CREATE OR REPLACE FUNCTION pg_temp._dba_uuid(seed text)", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertIn("ON CONFLICT (provider_id, provider) DO UPDATE", sql)
        self.assertIn("PUNKTB_PROD_DEV_REFRESH_REQUIRES_AUTH_USERS_WRITE", sql)
        self.assertIn("PUNKTB_PROD_DEV_REFRESH_REQUIRES_AUTH_IDENTITIES_WRITE", sql)
        self.assertIn("CREATE TEMP TABLE _stage_refresh_specialists", sql)
        self.assertIn("CREATE TEMP TABLE _stage_refresh_clients", sql)
        self.assertIn("CREATE TEMP TABLE _stage_refresh_results", sql)
        self.assertIn("INSERT INTO assess.specialists", sql)
        self.assertIn("INSERT INTO assess.clients", sql)
        self.assertIn("family_name", sql)
        self.assertIn("patronymic", sql)
        self.assertIn("birthdate", sql)
        self.assertIn("WITH normalized_clients AS", sql)
        self.assertIn("regexp_split_to_array", sql)
        self.assertIn("INSERT INTO assess.diag_results", sql)
        self.assertIn("pg_temp._dba_uuid('punktb-user-email:' || lower(btrim(s.email)))", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertNotIn("\\i '", sql)
        self.assertIn("ROLLBACK;", sql)
        self.assertNotIn("COMMIT;", sql)

    def test_punktb_prod_dev_refresh_target_sql_commits_apply(self) -> None:
        sql = dba._build_punktb_prod_dev_refresh_target_sql(Path("dump.sql"), dry_run=False)
        self.assertIn("COMMIT;", sql)
        self.assertNotIn("ROLLBACK;", sql)

    def test_punktb_prod_dev_refresh_profile_guardrails(self) -> None:
        source = dba.Profile(
            name="punktb-prod-ro",
            key="PUNKTB_PROD_RO",
            values={
                "PGHOST": "vds.punkt-b.pro",
                "PGDATABASE": "punkt_b_prod",
                "PGUSER": "db_readonly_prod",
                "PGPASSWORD": "secret",
                "WRITE_CLASS": "prod",
            },
        )
        target = dba.Profile(
            name="intdata-dev-admin",
            key="INTDATA_DEV_ADMIN",
            values={
                "PGHOST": "vds.intdata.pro",
                "PGDATABASE": "intdata",
                "PGUSER": "agents",
                "PGPASSWORD": "secret",
            },
        )
        dba._validate_punktb_prod_dev_refresh_profiles(source, target)

        wrong_source = dba.Profile(
            name="punktb-prod-admin",
            key="PUNKTB_PROD_ADMIN",
            values={
                "PGHOST": "vds.punkt-b.pro",
                "PGDATABASE": "punkt_b_prod",
                "PGUSER": "agents",
                "PGPASSWORD": "secret",
            },
        )
        with self.assertRaises(dba.DBAError):
            dba._validate_punktb_prod_dev_refresh_profiles(wrong_source, target)

    def test_read_manifest_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            init_dir = repo / "init"
            init_dir.mkdir(parents=True, exist_ok=True)
            (init_dir / "migration_manifest.lock").write_text(
                "20260405093000|first.sql|checksum\n20260405113000|second.sql|checksum\n",
                encoding="utf-8",
            )
            versions = dba._read_manifest_versions(repo)
        self.assertEqual(
            versions,
            [
                ("20260405093000", "first.sql"),
                ("20260405113000", "second.sql"),
            ],
        )

    def test_resolve_data_repo_uses_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            resolved = dba._resolve_data_repo(str(repo))
            self.assertEqual(resolved, repo.resolve())

    def test_resolve_data_repo_uses_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            previous = os.environ.get("DBA_DATA_REPO")
            os.environ["DBA_DATA_REPO"] = str(repo)
            try:
                resolved = dba._resolve_data_repo(None)
            finally:
                if previous is None:
                    os.environ.pop("DBA_DATA_REPO", None)
                else:
                    os.environ["DBA_DATA_REPO"] = previous
            self.assertEqual(resolved, repo.resolve())

    def test_resolve_data_repo_reads_local_env_file(self) -> None:
        previous_root = dba.TOOL_ROOT
        previous = os.environ.get("DBA_DATA_REPO")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "custom-data"
            repo.mkdir()
            tool_root = root / "tools" / "dba"
            tool_root.mkdir(parents=True, exist_ok=True)
            (tool_root / ".env").write_text(f"DBA_DATA_REPO={repo}\n", encoding="utf-8")
            dba.TOOL_ROOT = tool_root
            try:
                os.environ.pop("DBA_DATA_REPO", None)
                resolved = dba._resolve_data_repo(None)
            finally:
                dba.TOOL_ROOT = previous_root
                if previous is None:
                    os.environ.pop("DBA_DATA_REPO", None)
                else:
                    os.environ["DBA_DATA_REPO"] = previous
            self.assertEqual(resolved, repo.resolve())

    def test_resolve_data_repo_requires_hint_when_auto_not_found(self) -> None:
        previous_root = dba.TOOL_ROOT
        previous = os.environ.get("DBA_DATA_REPO")
        with tempfile.TemporaryDirectory() as tmpdir:
            dba.TOOL_ROOT = Path(tmpdir) / "tools" / "dba"
            try:
                os.environ.pop("DBA_DATA_REPO", None)
                with self.assertRaises(dba.DBAError):
                    dba._resolve_data_repo(None)
            finally:
                dba.TOOL_ROOT = previous_root
                if previous is None:
                    os.environ.pop("DBA_DATA_REPO", None)
                else:
                    os.environ["DBA_DATA_REPO"] = previous

    def test_resolve_data_repo_uses_non_windows_sibling_repo(self) -> None:
        previous_root = dba.TOOL_ROOT
        previous = os.environ.get("DBA_DATA_REPO")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "data"
            repo.mkdir()
            dba.TOOL_ROOT = root / "tools" / "dba"
            try:
                os.environ.pop("DBA_DATA_REPO", None)
                with mock.patch.object(dba.os, "name", "posix"):
                    resolved = dba._resolve_data_repo(None)
            finally:
                dba.TOOL_ROOT = previous_root
                if previous is None:
                    os.environ.pop("DBA_DATA_REPO", None)
                else:
                    os.environ["DBA_DATA_REPO"] = previous
            self.assertEqual(resolved, repo.resolve())

    def test_tool_tmp_dir_uses_master_tmp_root(self) -> None:
        previous_root = dba.TOOL_ROOT
        previous_int_root = dba.INT_ROOT
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dba.TOOL_ROOT = root / "tools" / "dba"
            dba.INT_ROOT = root
            try:
                tmp_path = dba._tool_tmp_dir("dumps")
            finally:
                dba.TOOL_ROOT = previous_root
                dba.INT_ROOT = previous_int_root
            self.assertEqual(tmp_path.parent.parent, root / ".tmp" / "tools" / "dba")
            self.assertTrue(tmp_path.exists())

    def test_resolve_data_repo_skips_windows_sibling_repo(self) -> None:
        previous_root = dba.TOOL_ROOT
        previous = os.environ.get("DBA_DATA_REPO")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data").mkdir()
            dba.TOOL_ROOT = root / "tools" / "dba"
            try:
                os.environ.pop("DBA_DATA_REPO", None)
                with mock.patch.object(dba.os, "name", "nt"):
                    with self.assertRaisesRegex(dba.DBAError, "dev@vds\\.intdata\\.pro:/int/data"):
                        dba._resolve_data_repo(None)
            finally:
                dba.TOOL_ROOT = previous_root
                if previous is None:
                    os.environ.pop("DBA_DATA_REPO", None)
                else:
                    os.environ["DBA_DATA_REPO"] = previous

    def test_run_process_keeps_secrets_in_env_not_in_argv(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object) -> object:
            captured["command"] = command
            captured["env"] = kwargs["env"]
            return dba.subprocess.CompletedProcess(command, 0, "", "")

        previous_run = dba.subprocess.run
        dba.subprocess.run = fake_run
        try:
            dba._run_process(
                ["psql", "--version"],
                env_map={
                    "PGPASSWORD": "secret",
                    "POSTGRES_PASSWORD": "other-secret",
                },
            )
        finally:
            dba.subprocess.run = previous_run

        command = captured["command"]
        env_map = captured["env"]
        self.assertEqual(command, ["psql", "--version"])
        self.assertNotIn("PGPASSWORD=secret", command)
        self.assertNotIn("POSTGRES_PASSWORD=other-secret", command)
        self.assertEqual(env_map["PGPASSWORD"], "secret")
        self.assertEqual(env_map["POSTGRES_PASSWORD"], "other-secret")

    def test_query_remote_versions_returns_empty_when_schema_migrations_missing(self) -> None:
        calls: list[list[str]] = []

        def fake_run_checked(argv: list[str], **kwargs: object) -> object:
            calls.append(argv)
            return dba.subprocess.CompletedProcess(argv, 0, "\n", "")

        profile = dba.Profile(
            name="intdata-dev",
            key="INTDATA_DEV",
            values={
                "PGHOST": "api.intdata.pro",
                "PGDATABASE": "intdata",
                "PGUSER": "dev_user",
                "PGPASSWORD": "secret",
            },
        )
        previous_run_checked = dba._run_checked
        previous_require_pg_command = dba._require_pg_command
        dba._run_checked = fake_run_checked
        dba._require_pg_command = lambda command_name: command_name
        try:
            versions = dba._query_remote_versions(profile)
        finally:
            dba._run_checked = previous_run_checked
            dba._require_pg_command = previous_require_pg_command

        self.assertEqual(versions, [])
        self.assertEqual(len(calls), 1)

    def test_require_pg_command_wraps_missing_binary(self) -> None:
        with mock.patch.object(dba, "_resolve_command", return_value=None):
            with self.assertRaises(dba.DBAError):
                dba._require_pg_command("psql")

    def test_require_bash_wraps_missing_binary(self) -> None:
        with mock.patch.object(dba, "WINDOWS_GIT_BASH_PATHS", tuple()):
            with mock.patch.object(dba.os, "name", "nt"):
                with mock.patch.object(dba.shutil, "which", return_value=None):
                    with self.assertRaises(dba.DBAError):
                        dba._require_bash()

    def test_require_bash_prefers_git_for_windows_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            git_bash = Path(tmpdir) / "bash.exe"
            git_bash.write_text("", encoding="utf-8")
            with mock.patch.object(dba, "WINDOWS_GIT_BASH_PATHS", (git_bash,)):
                with mock.patch.object(dba.os, "name", "nt"):
                    with mock.patch.object(dba.shutil, "which", return_value=r"C:\Windows\System32\bash.exe"):
                        self.assertEqual(dba._require_bash(), str(git_bash))

    def test_assert_owner_control_token_requires_exact_ack(self) -> None:
        with self.assertRaises(dba.DBAError):
            dba._assert_owner_control_token(None)
        with self.assertRaises(dba.DBAError):
            dba._assert_owner_control_token("wrong")
        dba._assert_owner_control_token(dba.OWNER_CONTROL_ACK)

    def test_resolve_supabase_command_uses_supabase_binary_first(self) -> None:
        with mock.patch.object(dba.shutil, "which", side_effect=[r"C:\supabase.exe", r"C:\npx.cmd"]):
            self.assertEqual(dba._resolve_supabase_command(), [r"C:\supabase.exe"])

    def test_resolve_supabase_command_falls_back_to_npx(self) -> None:
        with mock.patch.object(dba.shutil, "which", side_effect=[None, r"C:\npx.cmd"]):
            self.assertEqual(dba._resolve_supabase_command(), [r"C:\npx.cmd", "supabase"])

    def test_supabase_status_db_url_extracts_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            with mock.patch.object(
                dba,
                "_run_checked_capture",
                return_value=dba.subprocess.CompletedProcess(
                    ["supabase", "status"],
                    0,
                    "API URL: http://127.0.0.1:54321\nDB URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres\n",
                    "",
                ),
            ):
                value = dba._supabase_status_db_url(["supabase"], workspace)
        self.assertEqual(value, "postgresql://postgres:postgres@127.0.0.1:54322/postgres")

    def test_db_env_from_url_returns_full_postgres_env(self) -> None:
        env = dba._db_env_from_url("postgresql://postgres:secret@127.0.0.1:54322/postgres")
        self.assertEqual(env["POSTGRES_HOST"], "127.0.0.1")
        self.assertEqual(env["POSTGRES_PORT"], "54322")
        self.assertEqual(env["POSTGRES_DB"], "postgres")
        self.assertEqual(env["POSTGRES_USER"], "postgres")
        self.assertEqual(env["POSTGRES_PASSWORD"], "secret")
        self.assertEqual(env["PGPASSWORD"], "secret")
        self.assertEqual(env["LOCAL_TEST_DATABASE_URL"], "postgresql://postgres:secret@127.0.0.1:54322/postgres")

    def test_local_test_parser_requires_confirmation(self) -> None:
        parser = dba._build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["local-test", "run"])
        args = parser.parse_args(
            [
                "local-test",
                "run",
                "--confirm-owner-control",
                dba.OWNER_CONTROL_ACK,
            ]
        )
        self.assertEqual(args.local_test_command, "run")

    def test_local_test_run_passes_full_postgres_env_to_migration_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "data"
            (repo_root / "init").mkdir(parents=True, exist_ok=True)
            args = dba.argparse.Namespace(
                repo=str(repo_root),
                workdir=str(root / "workspace"),
                smoke_file=None,
                no_seed=True,
                keep_running=True,
                confirm_owner_control=dba.OWNER_CONTROL_ACK,
            )
            captured_calls: list[dict[str, object]] = []
            with mock.patch.object(dba, "_require_docker", return_value="docker"):
                with mock.patch.object(dba, "_resolve_supabase_command", return_value=["supabase"]):
                    with mock.patch.object(dba, "_supabase_status_db_url", return_value="postgresql://postgres:secret@127.0.0.1:54322/postgres"):
                        with mock.patch.object(dba, "_require_bash", return_value=r"C:\Program Files\Git\bin\bash.exe"):
                            with mock.patch.object(dba, "_run_checked", side_effect=lambda argv, **kwargs: captured_calls.append({"argv": argv, "kwargs": kwargs}) or dba.subprocess.CompletedProcess(argv, 0, "", "")):
                                exit_code = dba._cmd_local_test_run(args)
        self.assertEqual(exit_code, 0)
        self.assertEqual(captured_calls[0]["argv"], ["supabase", "init"])
        self.assertEqual(captured_calls[1]["argv"], ["supabase", "start"])
        migration_call = captured_calls[2]
        self.assertEqual(migration_call["argv"][0], r"C:\Program Files\Git\bin\bash.exe")
        self.assertEqual(migration_call["kwargs"]["extra_env"]["POSTGRES_HOST"], "127.0.0.1")
        self.assertEqual(migration_call["kwargs"]["extra_env"]["POSTGRES_PORT"], "54322")
        self.assertEqual(migration_call["kwargs"]["extra_env"]["POSTGRES_DB"], "postgres")
        self.assertEqual(migration_call["kwargs"]["extra_env"]["POSTGRES_USER"], "postgres")
        self.assertEqual(migration_call["kwargs"]["extra_env"]["POSTGRES_PASSWORD"], "secret")
        self.assertEqual(migration_call["kwargs"]["extra_env"]["PGPASSWORD"], "secret")

    def test_prepend_path_entry_moves_pg_bin_to_front(self) -> None:
        result = dba._prepend_path_entry(
            r"C:\Windows\System32;C:\Program Files\PostgreSQL\17\bin;C:\Tools",
            Path(r"C:\Program Files\PostgreSQL\17\bin"),
        )
        self.assertEqual(
            result,
            r"C:\Program Files\PostgreSQL\17\bin;C:\Windows\System32;C:\Tools",
        )

    def test_migrate_data_incremental_prepends_pg_bin_to_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_path = root / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DBA_PROFILE__SMOKE__PGHOST=api.intdata.pro",
                        "DBA_PROFILE__SMOKE__PGPORT=5432",
                        "DBA_PROFILE__SMOKE__PGDATABASE=intdata",
                        "DBA_PROFILE__SMOKE__PGUSER=dev_user",
                        "DBA_PROFILE__SMOKE__PGPASSWORD=secret",
                    ]
                ),
                encoding="utf-8",
            )
            repo_root = root / "data"
            (repo_root / "init").mkdir(parents=True, exist_ok=True)
            (repo_root / "init" / "010_supabase_migrate.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            args = dba.argparse.Namespace(
                target="smoke",
                approve_target="smoke",
                force_prod_write=False,
                repo=str(repo_root),
                mode="incremental",
                seed_business=False,
            )
            previous_root = dba.TOOL_ROOT
            captured: dict[str, object] = {}
            dba.TOOL_ROOT = root
            with mock.patch.object(dba, "_require_bash", return_value=r"C:\Program Files\Git\bin\bash.exe"):
                with mock.patch.object(dba, "_require_pg_command", return_value=r"C:\Program Files\PostgreSQL\17\bin\psql.exe"):
                    with mock.patch.object(dba, "_run_checked", side_effect=lambda argv, **kwargs: captured.update({"argv": argv, "kwargs": kwargs}) or dba.subprocess.CompletedProcess(argv, 0, "", "")):
                        try:
                            dba._cmd_migrate_data(args)
                        finally:
                            dba.TOOL_ROOT = previous_root

            self.assertEqual(captured["argv"][0], r"C:\Program Files\Git\bin\bash.exe")
            self.assertTrue(
                captured["kwargs"]["extra_env"]["PATH"].startswith(r"C:\Program Files\PostgreSQL\17\bin")
            )

    def test_migrate_data_bootstrap_passes_profile_password(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_path = root / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DBA_PROFILE__SMOKE__PGHOST=api.intdata.pro",
                        "DBA_PROFILE__SMOKE__PGPORT=5432",
                        "DBA_PROFILE__SMOKE__PGDATABASE=intdata",
                        "DBA_PROFILE__SMOKE__PGUSER=dev_user",
                        "DBA_PROFILE__SMOKE__PGPASSWORD=secret",
                    ]
                ),
                encoding="utf-8",
            )
            repo_root = root / "data"
            init_dir = repo_root / "init"
            init_dir.mkdir(parents=True, exist_ok=True)
            (init_dir / "schema.sql").write_text("select 1;\n", encoding="utf-8")
            args = dba.argparse.Namespace(
                target="smoke",
                approve_target="smoke",
                force_prod_write=False,
                repo=str(repo_root),
                mode="bootstrap",
                seed_business=False,
            )
            previous_root = dba.TOOL_ROOT
            calls: list[dict[str, object]] = []
            dba.TOOL_ROOT = root
            with mock.patch.object(dba, "_require_pg_command", return_value="psql"):
                with mock.patch.object(dba, "_run_checked", side_effect=lambda argv, **kwargs: calls.append({"argv": argv, "kwargs": kwargs}) or dba.subprocess.CompletedProcess(argv, 0, "", "")):
                    try:
                        dba._cmd_migrate_data(args)
                    finally:
                        dba.TOOL_ROOT = previous_root

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["kwargs"]["profile"].password, "secret")
            self.assertEqual(calls[0]["kwargs"]["extra_env"]["POSTGRES_PASSWORD"], "secret")

    def test_test_tcp_wraps_socket_errors(self) -> None:
        profile = dba.Profile(
            name="intdata-dev",
            key="INTDATA_DEV",
            values={
                "PGHOST": "127.0.0.1",
                "PGPORT": "1",
                "PGDATABASE": "postgres",
                "PGUSER": "postgres",
                "PGPASSWORD": "secret",
            },
        )
        with mock.patch.object(dba.socket, "create_connection", side_effect=ConnectionRefusedError("refused")):
            with self.assertRaises(dba.DBAError):
                dba._test_tcp(profile)


if __name__ == "__main__":
    unittest.main()
