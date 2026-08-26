import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


MODULE_PATH = (
    pathlib.Path(__file__).parents[2]
    / "codex"
    / "tools"
    / "prointdata-google-credentials"
    / "prointdata_google.py"
)
SPEC = importlib.util.spec_from_file_location("prointdata_google", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def token_payload():
    return {
        "client_id": "457108529638-8cl9djer1mpvna6ngg0lk471dq5md6k3.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "refresh_token": "test-refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    }


class BundleTests(unittest.TestCase):
    def test_bundle_has_redacted_stable_summary(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        summary = MODULE.safe_summary(bundle)
        self.assertEqual(summary["account"], "prointdata@gmail.com")
        self.assertEqual(summary["client_id_fp"], "9544e2cb1dc9")
        self.assertNotIn("refresh_token", json.dumps(summary))
        self.assertEqual(summary["scope_count"], 2)

    def test_rejects_wrong_client(self):
        payload = token_payload()
        payload["client_id"] = "other-client"
        with self.assertRaises(MODULE.CredentialError):
            MODULE.bundle_from_authorized_user(payload)

    def test_refresh_verifies_expected_account(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        responses = [
            {"access_token": "access", "expires_in": 3600},
            {"email": "prointdata@gmail.com"},
        ]
        with mock.patch.object(MODULE, "_http_json", side_effect=responses):
            result = MODULE.refresh_and_verify(bundle)
        self.assertEqual(result["access_token"], "access")

    def test_refresh_rejects_other_account(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        responses = [
            {"access_token": "access", "expires_in": 3600},
            {"email": "other@example.com"},
        ]
        with mock.patch.object(MODULE, "_http_json", side_effect=responses):
            with self.assertRaises(MODULE.CredentialError):
                MODULE.refresh_and_verify(bundle)

    def test_atomic_materialization_keeps_refresh_token_out_of_state(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            homes = [root / "main", root / "profile"]
            consumers = MODULE._materialize_hermes(
                bundle, "access", "2026-07-23T14:00:00+00:00", homes
            )
            state_path = root / "state.json"
            MODULE._write_state(state_path, bundle, consumers)
            state_text = state_path.read_text(encoding="utf-8")
            self.assertNotIn("test-refresh", state_text)
            for home in homes:
                payload = json.loads((home / "google_token.json").read_text())
                self.assertEqual(payload["refresh_token"], "test-refresh")

    def test_linux_defaults_include_existing_gateway_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            main = pathlib.Path(directory) / ".hermes"
            (main / "profiles" / "intbrain").mkdir(parents=True)
            (main / "profiles" / "intbridge").mkdir(parents=True)
            with (
                mock.patch.object(MODULE, "default_hermes_home", return_value=main),
                mock.patch.object(MODULE.os, "name", "posix"),
            ):
                self.assertEqual(
                    MODULE.default_hermes_homes(),
                    [
                        main,
                        main / "profiles" / "intbrain",
                        main / "profiles" / "intbridge",
                    ],
                )

    def test_hermes_files_roll_back_when_gog_import_fails(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            home = root / "main"
            home.mkdir()
            token_path = home / "google_token.json"
            token_path.write_text('{"old": true}', encoding="utf-8")
            verified = {
                "bundle": bundle,
                "access_token": "access",
                "expiry": "2026-07-23T14:00:00+00:00",
            }
            with (
                mock.patch.object(MODULE, "refresh_and_verify", return_value=verified),
                mock.patch.object(
                    MODULE, "_gog_import", side_effect=MODULE.CredentialError("failed")
                ),
            ):
                with self.assertRaises(MODULE.CredentialError):
                    MODULE.apply_consumers(
                        bundle,
                        homes=[home],
                        gog_bin="gog",
                        state_path=root / "state.json",
                    )
            self.assertEqual(token_path.read_text(encoding="utf-8"), '{"old": true}')

    def test_gws_receives_access_token_only_via_environment(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        verified = {
            "bundle": bundle,
            "access_token": "access-only-in-env",
            "expiry": "2026-07-23T14:00:00+00:00",
        }
        completed = mock.Mock(returncode=0)
        with (
            mock.patch.object(MODULE.shutil, "which", return_value="gws"),
            mock.patch.object(MODULE, "refresh_and_verify", return_value=verified),
            mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run,
        ):
            code = MODULE._run_gws(
                bundle,
                gws_bin="gws",
                gws_args=["drive", "files", "list"],
                credential_path=None,
            )
        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("access-only-in-env", command)
        self.assertEqual(environment["GOOGLE_WORKSPACE_CLI_TOKEN"], "access-only-in-env")

    def test_gog_import_omits_large_scope_metadata(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        completed = mock.Mock(returncode=0)
        with (
            mock.patch.object(MODULE.shutil, "which", return_value="gog"),
            mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run,
        ):
            self.assertEqual(MODULE._gog_import(bundle, "gog"), "gog:keyring")
        envelope = json.loads(run.call_args.kwargs["input"])
        self.assertNotIn("scopes", envelope)
        self.assertEqual(envelope["refresh_token"], "test-refresh")

    def test_systemd_decrypt_uses_matching_credential_name(self):
        bundle = MODULE.bundle_from_authorized_user(token_payload())
        completed = mock.Mock(returncode=0, stdout=MODULE._canonical_json(bundle))
        with mock.patch.object(
            MODULE.subprocess, "run", return_value=completed
        ) as run:
            self.assertEqual(
                MODULE._systemd_store_read(pathlib.Path("/tmp/bundle.cred")),
                bundle,
            )
        command = run.call_args.args[0]
        self.assertIn(
            f"--name={MODULE.SYSTEMD_CREDENTIAL_NAME}",
            command,
        )


if __name__ == "__main__":
    unittest.main()
