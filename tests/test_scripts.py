import contextlib
import hashlib
import http.server
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_iso
import citrix_mode
import iso_config
import packages
import session_setup
import shell_setup
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

    def test_payload_without_file_digest(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b"x" * (1024 ** 2 + 17)
            (root / "script").write_bytes(data)
            (root / "empty").write_bytes(b"")
            (root / "manifest.json").write_text(json.dumps({"files": {
                "script": hashlib.sha256(data).hexdigest(),
                "empty": hashlib.sha256(b"").hexdigest(),
            }}))
            with patch.object(hashlib, "file_digest", create=True):
                del hashlib.file_digest
                with contextlib.redirect_stdout(io.StringIO()):
                    iso_config.verify_payload(root)
                (root / "script").write_bytes(b"modified")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
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

    def test_password_too_short(self):
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.getpass.getpass", side_effect=["sim1234", "sim1234"]):
            with self.assertRaises(ValueError):
                build_iso.prompt_hash()

    def test_password_minimum_length_accepted(self):
        completed = subprocess.CompletedProcess([], 0, stdout=HASH + "\n", stderr="")
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.getpass.getpass", return_value="simul123"), patch("build_iso.run", return_value=completed):
            self.assertEqual(build_iso.prompt_hash(), HASH)

    def test_username_interactive_default(self):
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.input", return_value=""):
            result = build_iso.prompt_username("ubunturiri")
            self.assertEqual(result, "ubunturiri")

    def test_username_interactive_custom(self):
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.input", return_value="moncompte"):
            result = build_iso.prompt_username("ubunturiri")
            self.assertEqual(result, "moncompte")

    def test_username_pipe_rejected(self):
        with patch("build_iso.sys.stdin.isatty", return_value=False):
            with self.assertRaises(ValueError):
                build_iso.prompt_username("ubunturiri")

    def test_username_invalid_rejected(self):
        with patch("build_iso.sys.stdin.isatty", return_value=True), patch("build_iso.input", return_value="root"):
            with self.assertRaises(ValueError):
                build_iso.prompt_username("ubunturiri")

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

class DownloadTests(unittest.TestCase):
    def test_download_complete_200_ok(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"test file content for download"

            target = root / "downloaded.bin"
            url = "https://example.com/test"
            with patch("build_iso.urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.geturl.return_value = "https://example.com/test"
                mock_response.headers = {"Content-Length": str(len(content))}
                mock_response.read = MagicMock(side_effect=[content, b""])
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                build_iso.download(url, target)
                self.assertEqual(target.read_bytes(), content)
                self.assertFalse((Path(str(target) + ".part")).exists())

    def test_download_partial_206_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            full_content = b"0123456789" * 100
            part1 = full_content[:500]
            part2 = full_content[500:]

            target = root / "downloaded.bin"
            target_part = Path(str(target) + ".part")
            target_part.write_bytes(part1)

            url = "https://example.com/file"
            with patch("build_iso.urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 206
                mock_response.geturl.return_value = "https://example.com/file"
                mock_response.headers = {
                    "Content-Length": str(len(part2)),
                    "Content-Range": f"bytes 500-{len(full_content)-1}/{len(full_content)}"
                }
                mock_response.read = MagicMock(side_effect=[part2, b""])
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                build_iso.download(url, target)
                self.assertEqual(target.read_bytes(), full_content)
                self.assertFalse(target_part.exists())

    def test_download_200_instead_of_206_truncates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            full_content = b"0123456789" * 100
            part1 = full_content[:500]
            target = root / "downloaded.bin"
            target_part = Path(str(target) + ".part")
            target_part.write_bytes(part1)

            url = "https://example.com/file"
            with patch("build_iso.urllib.request.urlopen") as mock_urlopen:
                call_count = [0]
                def urlopen_side_effect(request, timeout=None):
                    call_count[0] += 1
                    response = MagicMock()
                    response.geturl.return_value = "https://example.com/file"
                    response.status = 200
                    response.headers = {"Content-Length": str(len(full_content))}
                    response.__enter__ = MagicMock(return_value=response)
                    response.__exit__ = MagicMock(return_value=False)
                    response.read = MagicMock(side_effect=[full_content, b""])
                    return response

                mock_urlopen.side_effect = urlopen_side_effect
                build_iso.download(url, target)
                self.assertEqual(target.read_bytes(), full_content)
                self.assertEqual(call_count[0], 1)

    def test_download_416_retry_without_range(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            full_content = b"0123456789" * 100
            part1 = full_content[:500]
            target = root / "downloaded.bin"
            target_part = Path(str(target) + ".part")
            target_part.write_bytes(part1)

            url = "https://example.com/file"
            with patch("build_iso.urllib.request.urlopen") as mock_urlopen:
                call_count = [0]
                def urlopen_side_effect(request, timeout=None):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        raise build_iso.urllib.error.HTTPError(url, 416, "Range Not Satisfiable", {}, None)
                    response = MagicMock()
                    response.geturl.return_value = "https://example.com/file"
                    response.status = 200
                    response.headers = {"Content-Length": str(len(full_content))}
                    response.__enter__ = MagicMock(return_value=response)
                    response.__exit__ = MagicMock(return_value=False)
                    response.read = MagicMock(side_effect=[full_content, b""])
                    return response

                mock_urlopen.side_effect = urlopen_side_effect
                build_iso.download(url, target)
                self.assertEqual(target.read_bytes(), full_content)
                self.assertEqual(call_count[0], 2)

    def test_download_206_content_range_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "downloaded.bin"
            target_part = Path(str(target) + ".part")
            target_part.write_bytes(b"partial")

            url = "https://example.com/file"
            with patch("build_iso.urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 206
                mock_response.geturl.return_value = "https://example.com/file"
                mock_response.headers = {
                    "Content-Length": "50",
                    "Content-Range": "bytes 7-106/200"
                }
                mock_response.read = MagicMock(side_effect=[b"x" * 50, b""])
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                with self.assertRaisesRegex(ValueError, "Content-Range incohérente"):
                    build_iso.download(url, target)

    def test_download_206_missing_content_range(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "downloaded.bin"
            target_part = Path(str(target) + ".part")
            target_part.write_bytes(b"partial")

            url = "https://example.com/file"
            with patch("build_iso.urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.status = 206
                mock_response.geturl.return_value = "https://example.com/file"
                mock_response.headers = {"Content-Length": "100"}
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                with self.assertRaisesRegex(ValueError, "Content-Range"):
                    build_iso.download(url, target)

    def test_check_space_sufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = build_iso.check_space(root, 1024)
            self.assertTrue(result)

    def test_check_space_insufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            huge_size = 1024 ** 4
            with self.assertRaisesRegex(ValueError, "Espace insuffisant"):
                build_iso.check_space(root, huge_size)

    def test_check_space_calculated_needs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            needed = int(3.9 * (1024 ** 3) + 2 * 325 * (1024 ** 2) + 512 * (1024 ** 2))
            with patch("shutil.disk_usage") as mock_du:
                mock_du.return_value = unittest.mock.MagicMock(free=14 * (1024 ** 3))
                result = build_iso.check_space(root, needed)
                self.assertTrue(result)
            with patch("shutil.disk_usage") as mock_du:
                mock_du.return_value = unittest.mock.MagicMock(free=int(3.5 * (1024 ** 3)))
                with self.assertRaisesRegex(ValueError, "Espace insuffisant"):
                    build_iso.check_space(root, needed)

    def test_official_iso_cache_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            iso_name = "ubuntu-24.04.1-live-server-amd64.iso"
            iso_path = cache / iso_name
            iso_content = b"fake iso content for testing cache reuse"
            iso_path.write_bytes(iso_content)
            iso_digest = hashlib.sha256(iso_content).hexdigest()
            sha256_content = f"{iso_digest}  {iso_name}\n"

            with patch("build_iso.download") as mock_download, \
                 patch("build_iso.run") as mock_run, \
                 patch("build_iso.select_iso", return_value=(iso_name, iso_digest)):
                mock_download.side_effect = lambda url, path, resume=True: (
                    path.write_text(sha256_content) if "SHA256SUMS" in str(url) else None
                )

                result = build_iso.official_iso(cache, None)
                self.assertEqual(result, iso_path)
                self.assertEqual(iso_path.read_bytes(), iso_content)
                mock_run.assert_called_once()
                mock_download.assert_called()


class PinTests(unittest.TestCase):

    def test_every_pin_is_https_with_sha256(self):
        for name, pin in packages.PINS.items():
            self.assertTrue(pin["url"].startswith("https://"), name)
            self.assertRegex(pin["sha256"], r"^[0-9a-f]{64}$", name)
            self.assertTrue(name.startswith("extras/"), name)
            self.assertNotIn("..", name)

    def test_fetch_pins_rejects_wrong_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            payload = root / "payload"
            payload.mkdir()
            fake = {"extras/thing.bin": {"version": "1", "url": "https://example.invalid/thing.bin", "sha256": "0" * 64}}

            def fake_download(url, path, resume=True):
                path.write_bytes(b"contenu inattendu")

            with patch("build_iso.PINS", fake), patch("build_iso.download", side_effect=fake_download):
                with self.assertRaisesRegex(ValueError, "SHA-256 inattendu"):
                    build_iso.fetch_pins(payload, cache)

    def test_fetch_pins_copies_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            payload = root / "payload"
            payload.mkdir()
            body = b"charge utile"
            digest = hashlib.sha256(body).hexdigest()
            fake = {"extras/thing.bin": {"version": "1.0", "url": "https://example.invalid/thing.bin", "sha256": digest}}
            calls = []

            def fake_download(url, path, resume=True):
                calls.append(url)
                path.write_bytes(body)

            with patch("build_iso.PINS", fake), patch("build_iso.download", side_effect=fake_download), contextlib.redirect_stdout(io.StringIO()):
                build_iso.fetch_pins(payload, cache)
                self.assertEqual((payload / "extras/thing.bin").read_bytes(), body)
                build_iso.fetch_pins(payload, cache)
            self.assertEqual(len(calls), 1)

    def test_fetch_pins_discards_corrupted_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            payload = root / "payload"
            payload.mkdir()
            body = b"charge utile"
            digest = hashlib.sha256(body).hexdigest()
            fake = {"extras/thing.bin": {"version": "1.0", "url": "https://example.invalid/thing.bin", "sha256": digest}}
            (cache / "1.0-thing.bin").write_bytes(b"cache corrompu")

            with patch("build_iso.PINS", fake), patch("build_iso.download", side_effect=lambda url, path, resume=True: path.write_bytes(body)), contextlib.redirect_stdout(io.StringIO()):
                build_iso.fetch_pins(payload, cache)
            self.assertEqual((payload / "extras/thing.bin").read_bytes(), body)


class PackageListTests(unittest.TestCase):

    def test_apt_groups_are_plain_names(self):
        for group, names in packages.APT_GROUPS.items():
            self.assertTrue(names, group)
            for name in names:
                self.assertRegex(name, r"^[a-z0-9][a-z0-9+.-]*$", f"{group} : {name}")

    def test_unknown_group_rejected(self):
        with self.assertRaises(ValueError):
            packages.apt_list("inexistant")

    def test_brave_source_is_deb822_with_keyring(self):
        self.assertIn("Signed-By: /usr/share/keyrings/brave-browser-archive-keyring.gpg", packages.BRAVE_SOURCE)
        self.assertIn("Types: deb\n", packages.BRAVE_SOURCE)
        self.assertNotIn("[trusted=yes]", packages.BRAVE_SOURCE)

    def test_cli_matches_python_api(self):
        script = Path(packages.__file__)
        for group in packages.APT_GROUPS:
            output = subprocess.run([sys.executable, str(script), "--apt", group], capture_output=True, text=True, check=True)
            self.assertEqual(output.stdout.strip(), packages.apt_list(group))
        output = subprocess.run([sys.executable, str(script), "--brave-package"], capture_output=True, text=True, check=True)
        self.assertEqual(output.stdout.strip(), packages.BRAVE_PACKAGE)


class ShellSetupTests(unittest.TestCase):

    def test_user_setup_refuses_root(self):
        with patch("shell_setup.os.geteuid", return_value=0):
            with self.assertRaisesRegex(ValueError, "pas root"):
                shell_setup.configure_user()

    def test_system_setup_requires_root(self):
        with patch("shell_setup.os.geteuid", return_value=1000):
            with self.assertRaisesRegex(ValueError, "réservée"):
                shell_setup.system("ubunturiri")

    def test_user_setup_backs_up_existing_bashrc(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            files = Path(temporary) / "files"
            files.mkdir()
            for name in ["bashrc", "starship.toml", "ghostty-config"]:
                (files / name).write_text(f"contenu {name}\n")
            (files / "nvim/lua/ubunturiri").mkdir(parents=True)
            (files / "nvim/init.lua").write_text("-- simulation\n")
            (files / "nvim/lua/ubunturiri/options.lua").write_text("-- simulation\n")
            home.mkdir()
            (home / ".bashrc").write_text("bashrc Ubuntu d’origine\n")
            with patch("shell_setup.FILES", files), patch("shell_setup.os.geteuid", return_value=1000), patch("shell_setup.Path.home", return_value=home), contextlib.redirect_stdout(io.StringIO()):
                shell_setup.configure_user()
            self.assertEqual((home / ".bashrc.ubuntu-origine").read_text(), "bashrc Ubuntu d’origine\n")
            self.assertEqual((home / ".bashrc").read_text(), "contenu bashrc\n")
            self.assertTrue((home / ".config/starship.toml").is_file())
            self.assertTrue((home / ".config/ghostty/config").is_file())
            self.assertTrue((home / ".bashrc.local").is_file())
            self.assertTrue((home / ".config/nvim/init.lua").is_file())
            self.assertTrue((home / ".config/nvim/lua/ubunturiri/options.lua").is_file())

    def test_user_setup_reports_missing_payload_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            with patch("shell_setup.FILES", Path(temporary) / "absent"), patch("shell_setup.os.geteuid", return_value=1000), patch("shell_setup.Path.home", return_value=home):
                with self.assertRaisesRegex(ValueError, "absent du contenu embarqué"):
                    shell_setup.configure_user()


class NetworkRendererTests(unittest.TestCase):

    def system_calls(self):
        """Exécute session_setup.system() en simulant la cible, et renvoie les systemctl."""
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ["usr/share/xsessions", "etc/gdm3", "etc/netplan", "usr/local/bin",
                              "var/lib/AccountsService/users", "etc/xdg/autostart", "opt/ubunturiri"]:
                (root / directory).mkdir(parents=True, exist_ok=True)
            (root / "usr/share/xsessions/gnome-xorg.desktop").write_text("[Desktop Entry]\n")
            for script in ["theme.py", "citrix_mode.py", "doctor.py"]:
                (root / "opt/ubunturiri" / script).write_text("#!/usr/bin/env python3\n")
            real_path = session_setup.Path

            def fake_path(*parts):
                joined = real_path(*parts)
                if joined.is_absolute():
                    return root / joined.relative_to("/")
                return joined

            with patch("session_setup.os.geteuid", return_value=0), \
                 patch("session_setup.pwd.getpwnam"), \
                 patch("session_setup.PAYLOAD", root / "opt/ubunturiri"), \
                 patch("session_setup.Path", side_effect=fake_path), \
                 patch("session_setup.subprocess.run", side_effect=lambda args, **kw: calls.append(args)):
                session_setup.system("ubunturiri")
        return [call for call in calls if call and call[0] == "systemctl"]

    def test_networkd_wait_online_is_masked_and_replaced(self):
        calls = self.system_calls()
        self.assertIn(["systemctl", "mask", "systemd-networkd-wait-online.service"], calls)
        self.assertIn(["systemctl", "enable", "NetworkManager-wait-online.service"], calls)

    def test_networkd_itself_is_left_alone(self):
        # Retirer l'attente suffit : changer qui gère les interfaces serait un
        # effet de bord non demandé.
        for call in self.system_calls():
            self.assertNotIn("systemd-networkd.service", call)
            self.assertNotIn("systemd-networkd.socket", call)

    def test_renderer_switch_and_wait_fix_stay_together(self):
        source = (build_iso.ROOT / "scripts/session_setup.py").read_text()
        self.assertLess(source.index("renderer: NetworkManager"),
                        source.index("systemd-networkd-wait-online.service"))


class InstallerDiagnosticsTests(unittest.TestCase):

    def setUp(self):
        self.path = build_iso.ROOT / "scripts/install-desktop.sh"
        self.text = self.path.read_text()

    def test_syntax_is_valid_bash(self):
        subprocess.run(["bash", "-n", str(self.path)], check=True)

    def test_logging_is_armed_before_the_first_step(self):
        self.assertIn('exec > >(tee -a "$LOG") 2>&1', self.text)
        self.assertIn("""trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR""", self.text)
        self.assertLess(self.text.index("trap 'on_error"), self.text.index("apt-get update"))

    def test_logging_failure_does_not_abort_the_install(self):
        # Une redirection exec qui échoue tuerait le script avant la première
        # étape : le chemin doit être testé avant d'être utilisé.
        guard = self.text.index(': >> "$LOG" 2>/dev/null')
        self.assertLess(guard, self.text.index('exec > >(tee -a "$LOG")'))
        self.assertIn("LOG='(indisponible)'", self.text)

    def test_font_check_does_not_depend_on_the_fontconfig_cache(self):
        # « fc-list | grep » échouait dans le chroot alors que les polices
        # étaient installées, et arrêtait toute l'installation après Starship.
        code = "\n".join(line for line in self.text.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("fc-list", code)
        self.assertIn("fc-scan --format '%{family}\\n'", code)
        self.assertIn("JetBrainsMonoNerdFontMono-Regular.ttf", self.text)

    def test_fc_cache_failure_is_only_a_warning(self):
        block = self.text[self.text.index("fc-cache"):]
        self.assertTrue(block.startswith("fc-cache -f \"$FONT_DIR\" >/dev/null 2>&1; then")
                        or "if ! fc-cache" in self.text)
        self.assertIn("Avertissement : fc-cache a échoué", self.text)
        # Aucun exit entre le fc-cache et l'étape suivante.
        bloc = self.text[self.text.index("if ! fc-cache"):]
        bloc = bloc[:bloc.index("\nfi\n") + 4]
        self.assertNotIn("exit", bloc)

    def test_every_step_is_announced_through_the_logged_helper(self):
        self.assertGreaterEqual(self.text.count("\nstep '"), 9)
        self.assertIn("=== ubunturiri : %s ===", self.text)


class PurgeAndMaintenanceTests(unittest.TestCase):

    def setUp(self):
        self.text = (build_iso.ROOT / "scripts/install-desktop.sh").read_text()

    def test_purge_removes_payload_but_keeps_the_runtime(self):
        purge = self.text[self.text.index("step 'Purge du contenu embarqué'"):]
        for jetable in ["$PAYLOAD/extras", "$PAYLOAD/pop-shell", "$PAYLOAD/icaclient.deb"]:
            self.assertIn(jetable, purge)
        # theme.py lit themes/ à chaque ouverture de session, l'autostart appelle
        # session_setup.py : les supprimer casserait le poste.
        for garde in ["theme.py", "citrix_mode.py", "session_setup.py", "shell_setup.py", "doctor.py", "themes", "files"]:
            self.assertIn(garde, purge)

    def test_purge_runs_after_the_session_is_configured(self):
        self.assertLess(self.text.index("step 'Configuration de la session GNOME et du shell'"),
                        self.text.index("step 'Purge du contenu embarqué'"))

    def test_unattended_upgrades_covers_brave(self):
        self.assertIn('"Brave Software:stable";', self.text)
        self.assertIn('APT::Periodic::Unattended-Upgrade "1";', self.text)
        self.assertIn("systemctl enable unattended-upgrades.service", self.text)
        self.assertIn("Automatic-Reboot \"false\"", self.text)


class DoctorTests(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, str(build_iso.ROOT / "scripts"))
        import doctor
        self.doctor = doctor

    def test_every_check_is_registered(self):
        source = (build_iso.ROOT / "scripts/doctor.py").read_text()
        controles = [nom for nom in dir(self.doctor) if nom.startswith("controler_")]
        self.assertGreaterEqual(len(controles), 8)
        for nom in controles:
            self.assertIn(nom, source.split("for controle in [")[1])

    def test_failures_exit_non_zero_and_carry_a_remedy(self):
        rapport = self.doctor.Rapport(quiet=True)
        with contextlib.redirect_stdout(io.StringIO()):
            rapport.echec("réseau", "quelque chose manque", "voici comment le réparer")
            self.assertEqual(rapport.verdict(), 1)
        self.assertEqual(len(rapport.echecs), 1)
        self.assertTrue(all(entree[2] for entree in rapport.echecs))

    def test_clean_report_exits_zero(self):
        rapport = self.doctor.Rapport(quiet=True)
        with contextlib.redirect_stdout(io.StringIO()):
            rapport.ok("shell", "tout va bien")
            self.assertEqual(rapport.verdict(), 0)

    def test_missing_command_never_raises(self):
        self.assertIsNone(self.doctor.sortie(["/commande/qui/nexiste/pas"]))

    def test_exposed_as_a_command(self):
        source = (build_iso.ROOT / "scripts/session_setup.py").read_text()
        self.assertIn('("ubunturiri-doctor", "doctor.py")', source)


class NeovimConfigTests(unittest.TestCase):

    RACINE = None

    def setUp(self):
        self.RACINE = build_iso.ROOT / "scripts/files/nvim"

    def test_expected_files_are_present(self):
        for relatif in ["init.lua", "lua/ubunturiri/options.lua", "lua/ubunturiri/plugins.lua",
                        "lua/ubunturiri/lsp.lua", "lua/ubunturiri/keymaps.lua",
                        "lsp/pylsp.lua", "lsp/ruff.lua", "lsp/marksman.lua"]:
            self.assertTrue((self.RACINE / relatif).is_file(), relatif)

    def test_init_loads_every_module(self):
        init = (self.RACINE / "init.lua").read_text()
        for module in ["options", "plugins", "lsp", "keymaps"]:
            self.assertIn(f"require('ubunturiri.{module}')", init)
        self.assertLess(init.index("mapleader"), init.index("require('ubunturiri.options')"))

    def test_server_files_return_a_command(self):
        for nom, binaire in [("pylsp", "pylsp"), ("ruff", "ruff"), ("marksman", "marksman")]:
            contenu = (self.RACINE / f"lsp/{nom}.lua").read_text()
            self.assertIn("return {", contenu)
            self.assertIn(f"'{binaire}'", contenu)
            self.assertIn("filetypes", contenu)
            self.assertIn("root_markers", contenu)

    def test_lint_is_not_duplicated_between_pylsp_and_ruff(self):
        pylsp = (self.RACINE / "lsp/pylsp.lua").read_text()
        for greffon in ["pycodestyle", "pyflakes", "mccabe", "autopep8", "yapf"]:
            self.assertRegex(pylsp, greffon + r" = \{ enabled = false \}")

    def test_no_third_party_plugin_manager(self):
        # vim.pack est natif depuis 0.12 : la présence de lazy.nvim ou packer
        # signalerait un retour en arrière.
        for fichier in self.RACINE.rglob("*.lua"):
            code = "\n".join(l for l in fichier.read_text().splitlines() if not l.lstrip().startswith("--"))
            for ancien in ["lazy.nvim", "packer.nvim", "vim-plug", "nvim-lspconfig", "mason.nvim"]:
                self.assertNotIn(ancien, code, f"{fichier.name} : {ancien}")
        self.assertIn("vim.pack.add", (self.RACINE / "lua/ubunturiri/plugins.lua").read_text())

    def test_treesitter_install_is_idempotent(self):
        plugins = (self.RACINE / "lua/ubunturiri/plugins.lua").read_text()
        self.assertIn("nvim_get_runtime_file('parser/'", plugins)
        self.assertIn("#manquants > 0", plugins)

    def test_config_is_embedded_and_installed(self):
        source = (build_iso.ROOT / "scripts/build_iso.py").read_text()
        self.assertIn('shutil.copytree(ROOT / "scripts/files", payload / "files")', source)
        shell = (build_iso.ROOT / "scripts/shell_setup.py").read_text()
        self.assertIn('copier_arbre(FILES / "nvim", home / ".config/nvim")', shell)
        self.assertIn('copier_arbre(FILES / "nvim", SKEL / ".config/nvim")', shell)


class BashrcTests(unittest.TestCase):

    def setUp(self):
        self.text = (build_iso.ROOT / "scripts/files/bashrc").read_text()

    def test_syntax_is_valid_bash(self):
        subprocess.run(["bash", "-n", str(build_iso.ROOT / "scripts/files/bashrc")], check=True)

    def test_ble_attach_is_the_last_statement(self):
        statements = [line for line in self.text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(statements[-1], "fi")
        self.assertIn("ble-attach", statements[-2])
        self.assertLess(self.text.index("--noattach"), self.text.index("starship init bash"))
        self.assertLess(self.text.index("starship init bash"), self.text.rindex("ble-attach"))

    def test_returns_early_when_not_interactive(self):
        self.assertLess(self.text.index("*) return ;;"), self.text.index("/usr/share/blesh/ble.sh"))

    def test_no_trailing_comment_after_a_value(self):
        for number, line in enumerate(self.text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            quote = None
            for index, character in enumerate(line):
                if quote:
                    quote = None if character == quote else quote
                elif character in "'\"":
                    quote = character
                elif character == "#" and index and line[index - 1].isspace():
                    self.fail(f"commentaire en fin de ligne {number} : {line}")


if __name__ == "__main__":
    unittest.main()
