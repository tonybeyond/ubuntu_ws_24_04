import contextlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_iso
import citrix_mode
import iso_config
import session_setup
import theme

HASH = "$6$simulation$" + "a" * 86


class PreflightTests(unittest.TestCase):
    def test_root_policy_and_cli(self):
        with patch("build_iso.platform.system", return_value="Linux"), patch("build_iso.platform.freedesktop_os_release", return_value={"ID": "ubuntu", "VERSION_ID": "24.04"}), patch("build_iso.sys.version_info", (3, 12)), patch("build_iso.shutil.which", return_value="/usr/bin/tool"), patch.object(Path, "is_file", return_value=True), patch("build_iso.os.geteuid", return_value=0), patch("build_iso.os.umask"), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, "--allow-root"):
                build_iso.main(["--check"])
            build_iso.main(["--allow-root", "--check"])
            self.assertIn("construction autorisée en root", output.getvalue())
            with patch("build_iso.os.geteuid", return_value=1000):
                build_iso.main(["--check"])
            with patch("build_iso.platform.freedesktop_os_release", return_value={"ID": "ubuntu", "VERSION_ID": "22.04"}):
                with self.assertRaises(ValueError):
                    build_iso.main(["--allow-root", "--check"])
            with patch("build_iso.shutil.which", return_value=None):
                with self.assertRaises(ValueError):
                    build_iso.main(["--allow-root", "--check"])


class ConfigurationTests(unittest.TestCase):
    def test_identity_validation(self):
        for user in ["root", "../user", "user;id", "", "A"]:
            with self.assertRaises(ValueError):
                iso_config.identity(user, "ubunturiri", HASH)
        with self.assertRaises(ValueError):
            iso_config.identity("ubunturiri", "bad/name", HASH)
        with self.assertRaises(ValueError):
            iso_config.identity("ubunturiri", "ubunturiri", "not-a-hash")

    def test_autoinstall_security(self):
        config = iso_config.autoinstall("ubunturiri", "ubunturiri", HASH)
        data = config["autoinstall"]
        self.assertEqual(data["identity"]["password"], HASH)
        self.assertEqual(data["interactive-sections"], ["network", "storage"])
        self.assertNotIn("password", data["storage"]["layout"])
        self.assertFalse(data["ssh"]["install-server"])
        self.assertIn("verify-encryption", data["late-commands"][0])
        self.assertEqual(json.loads(json.dumps(config)), config)

    def test_grub_patch_preserves_other_entries(self):
        original = 'menuentry "Ubuntu" {\n linux /casper/vmlinuz quiet ---\n}\nmenuentry "UEFI" { fwsetup }\n'
        result = iso_config.patch_grub(original)
        self.assertIn("quiet autoinstall subiquity.autoinstallpath=cdrom/autoinstall.yaml ---", result)
        self.assertIn('menuentry "UEFI" { fwsetup }', result)
        with self.assertRaises(ValueError):
            iso_config.patch_grub(result)
        with self.assertRaises(ValueError):
            iso_config.patch_grub("linux /unexpected/kernel ---\n")

    def test_hwe_grub_entry(self):
        self.assertIn("autoinstall", iso_config.patch_grub("\tlinux /casper/hwe-vmlinuz ---\n"))

    def test_iso_selection(self):
        values = "a" * 64 + " *ubuntu-24.04.2-live-server-amd64.iso\n" + "b" * 64 + "  ubuntu-24.04.10-live-server-amd64.iso\n"
        self.assertEqual(build_iso.select_iso(values), ("ubuntu-24.04.10-live-server-amd64.iso", "b" * 64))
        with self.assertRaises(ValueError):
            build_iso.select_iso("a" * 64 + " ubuntu-26.04-live-server-amd64.iso")

    def test_encrypted_ancestry(self):
        disk = {"type": "disk", "fstype": None}
        luks = {"type": "part", "fstype": "crypto_LUKS", "children": [disk]}
        crypt = {"type": "crypt", "children": [luks]}
        self.assertTrue(iso_config.encrypted_tree({"type": "lvm", "children": [crypt]}))
        self.assertFalse(iso_config.encrypted_tree({"type": "lvm", "children": [disk]}))
        self.assertFalse(iso_config.encrypted_tree({"type": "lvm", "children": [crypt, disk]}))
        self.assertFalse(iso_config.encrypted_tree({"type": "crypt", "children": [disk]}))

    def test_root_encryption_validation(self):
        tree = {"blockdevices": [{"type": "lvm", "children": [{"type": "crypt", "children": [{"type": "part", "fstype": "crypto_LUKS"}]}]}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "etc").mkdir()
            (root / "etc/crypttab").write_text("cryptroot UUID=example none luks\n")
            with patch("iso_config.subprocess.check_output", side_effect=["/dev/mapper/root\n", json.dumps(tree)]), contextlib.redirect_stdout(io.StringIO()):
                iso_config.verify_encryption(directory)
            (root / "etc/crypttab").write_text("cryptroot UUID=example /boot/key luks\n")
            with patch("iso_config.subprocess.check_output", side_effect=["/dev/mapper/root\n", json.dumps(tree)]):
                with self.assertRaises(ValueError):
                    iso_config.verify_encryption(directory)

    def test_payload_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "script"
            data.write_text("original")
            (root / "manifest.json").write_text(json.dumps({"files": {"script": build_iso.sha256(data)}}))
            with contextlib.redirect_stdout(io.StringIO()):
                iso_config.verify_payload(root)
            data.write_text("modifié")
            with self.assertRaises(ValueError):
                iso_config.verify_payload(root)

    def test_archive_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.tar"
            with tarfile.open(archive, "w") as stream:
                entry = tarfile.TarInfo("../../escape")
                entry.size = 1
                stream.addfile(entry, io.BytesIO(b"x"))
            destination = root / "out"
            destination.mkdir()
            with self.assertRaises(tarfile.FilterError):
                build_iso.unpack(archive, destination)
            self.assertFalse((root / "escape").exists())

    def test_password_hash_never_printed(self):
        completed = subprocess.CompletedProcess([], 0, stdout=HASH + "\n", stderr="")
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.getpass.getpass", return_value="simulation-only-not-a-secret"), patch("build_iso.run", return_value=completed) as runner, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(build_iso.prompt_hash(), HASH)
            self.assertNotIn(HASH, output.getvalue())
            self.assertEqual(runner.call_args.args[0], ["openssl", "passwd", "-6", "-stdin"])
            self.assertNotIn("simulation-only-not-a-secret", runner.call_args.args[0])

    def test_password_mismatch_rejected(self):
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.getpass.getpass", side_effect=["simulation-a", "simulation-b"]):
            with self.assertRaises(ValueError):
                build_iso.prompt_hash()

    def test_password_pipe_rejected(self):
        with patch("build_iso.sys.stdin.isatty", return_value=False):
            with self.assertRaises(ValueError):
                build_iso.prompt_hash()


class AssemblyTests(unittest.TestCase):
    def test_assembly_maps_and_boot_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload"
            payload.mkdir()
            (payload / "sample").write_text("contenu")
            config = iso_config.autoinstall("ubunturiri", "ubunturiri", HASH)
            def execute(args, **kwargs):
                if "-extract" in args:
                    target = Path(args[-1])
                    if args[-2] == "/boot/grub/grub.cfg":
                        target.write_text("linux /casper/vmlinuz ---\n")
                    elif args[-2] == "/md5sum.txt":
                        target.write_text("0" * 32 + "  ./boot/grub/grub.cfg\n")
                return subprocess.CompletedProcess(args, 0)
            with patch("build_iso.run", side_effect=execute) as runner:
                build_iso.assemble(root / "source.iso", root, payload, config, root / "output.iso")
                args = runner.call_args.args[0]
            self.assertGreater(args.index("replay"), args.index("/md5sum.txt"))
            self.assertEqual(json.loads((root / "autoinstall.yaml").read_text()), config)
            self.assertIn("./payload/sample", (root / "md5sum.txt").read_text())
            self.assertNotIn("0" * 32, (root / "md5sum.txt").read_text())

    def test_safe_source_symlink_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.tar"
            with tarfile.open(archive, "w") as stream:
                entry = tarfile.TarInfo("source/file")
                entry.size = 1
                stream.addfile(entry, io.BytesIO(b"x"))
                link = tarfile.TarInfo("source/link")
                link.type = tarfile.SYMTYPE
                link.linkname = "file"
                stream.addfile(link)
            destination = root / "extracted"
            destination.mkdir()
            result = build_iso.unpack(archive, destination)
            self.assertEqual((result / "link").read_bytes(), b"x")


class SessionTests(unittest.TestCase):
    def test_citrix_restore_exact_values(self):
        values = [["schema", "key", "['<Super>a']", "[]"]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with patch("citrix_mode.snapshot", return_value=values), patch("citrix_mode.settings") as setter:
                citrix_mode.activate(path)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                setter.assert_called_with("set", "schema", "key", "[]")
                self.assertTrue(citrix_mode.restore(path))
                setter.assert_called_with("set", "schema", "key", "['<Super>a']")
                self.assertFalse(path.exists())

    def test_citrix_rollback_on_failure(self):
        values = [["schema", "key", "['<Super>a']", "[]"]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            failure = subprocess.CalledProcessError(1, "gsettings")
            with patch("citrix_mode.snapshot", return_value=values), patch("citrix_mode.settings", side_effect=[failure, ""]):
                with self.assertRaises(subprocess.CalledProcessError):
                    citrix_mode.activate(path)
                self.assertFalse(path.exists())

    def test_theme_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "themes/test/colors.toml"
            source.parent.mkdir(parents=True)
            source.write_text('background = "#101010"\nforeground = "#eeeeee"\naccent = "#123456"\n')
            def fake(action, schema, key, value=None):
                return "'b1dcc9dd-5262-4d8d-a863-c897e6d979b9'" if action == "get" else ""
            with patch("theme.THEMES", root / "themes"), patch("theme.Path.home", return_value=root), patch("theme.settings", side_effect=fake) as setter, contextlib.redirect_stdout(io.StringIO()):
                theme.apply_theme("test")
                setter.assert_any_call("set", theme.POP_ID, "hint-color-rgba", "'#123456'")
            self.assertEqual((root / ".local/state/ubunturiri/theme").read_text(), "test\n")

    def test_user_setup_without_root_or_live_session(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            def fake(action, schema, key, value=None):
                return "@as []" if action == "get" else ""
            with patch("session_setup.os.geteuid", return_value=1000), patch("session_setup.Path.home", return_value=home), patch("session_setup.settings", side_effect=fake) as setter, patch("session_setup.subprocess.run"):
                session_setup.configure_user()
                setter.assert_any_call("set", session_setup.POP_ID, "tile-by-default", "true")
            config = json.loads((home / ".config/pop-shell/config.json").read_text())
            self.assertIn("wfica", config["float"][0]["class"])
            self.assertTrue((home / ".local/state/ubunturiri/configured").exists())


if __name__ == "__main__":
    unittest.main()
