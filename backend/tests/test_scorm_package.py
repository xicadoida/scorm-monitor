import asyncio
import io
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scorm_package import InvalidPackage, extract_package, prepare_package, validate_course_code
from scorm_fixtures import SCORM12


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, extra=None, base=True, compression=zipfile.ZIP_STORED):
        path = self.root / 'input.zip'
        with zipfile.ZipFile(path, 'w', compression=compression) as z:
            if base:
                z.writestr('imsmanifest.xml', SCORM12)
                z.writestr('scormdriver/indexAPI.html', '<html/>')
            for name, data in (extra or []):
                if isinstance(name, str) and '\\' in name:
                    info = zipfile.ZipInfo('placeholder')
                    info.filename = name
                    name = info
                z.writestr(name, data)
        return path

    def extract(self, path):
        return extract_package(path, self.root / 'out')

    def test_valid_package(self):
        root = self.extract(self.archive())
        self.assertEqual((Path(root) / 'scormdriver/indexAPI.html').read_text(), '<html/>')

    def test_nested_package(self):
        root = self.extract(self.archive([('course/imsmanifest.xml', SCORM12), ('course/scormdriver/indexAPI.html', 'ok')], base=False))
        self.assertEqual(Path(root).name, 'course')

    def test_invalid_zip(self):
        path = self.root / 'broken.zip'
        path.write_bytes(b'not a zip')
        with self.assertRaises(InvalidPackage):
            self.extract(path)

    def test_truncated_zip(self):
        path = self.archive()
        path.write_bytes(path.read_bytes()[:-30])
        with self.assertRaises(InvalidPackage):
            self.extract(path)

    def test_unsafe_paths(self):
        for name in ['../escape', '/absolute', 'C:/drive', 'a\\evil', 'a/../evil', 'a//evil', 'a./evil', 'NUL.txt', 'x:stream', 'x\x01']:
            with self.subTest(name=name), self.assertRaises(InvalidPackage):
                self.extract(self.archive([(name, 'bad')]))
        self.assertFalse((self.root / 'out').exists())

    def test_suspicious_files(self):
        for name in ['evil.php', '.htaccess', 'dir/.user.ini', 'run.exe']:
            with self.subTest(name=name), self.assertRaises(InvalidPackage):
                self.extract(self.archive([(name, 'bad')]))

    def test_symlink(self):
        info = zipfile.ZipInfo('link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(InvalidPackage):
            self.extract(self.archive([(info, '/outside')]))

    def test_duplicate_case_alias(self):
        with self.assertRaises(InvalidPackage):
            self.extract(self.archive([('IMSMANIFEST.XML', 'bad')]))

    def test_missing_manifest(self):
        with self.assertRaises(InvalidPackage):
            self.extract(self.archive(base=False))

    def test_multiple_manifests(self):
        with self.assertRaises(InvalidPackage):
            self.extract(self.archive([('other/imsmanifest.xml', '<manifest/>')]))

    def test_missing_launcher(self):
        with self.assertRaises(InvalidPackage):
            self.extract(self.archive([('imsmanifest.xml', SCORM12)], base=False))

    def test_limits(self):
        for key in ['SCORM_MAX_ENTRIES', 'SCORM_MAX_FILE_BYTES', 'SCORM_MAX_EXTRACTED_BYTES']:
            with self.subTest(key=key), patch.dict(os.environ, {key: '1'}), self.assertRaises(InvalidPackage):
                self.extract(self.archive())

    def test_expansion_ratio(self):
        with self.assertRaises(InvalidPackage):
            self.extract(self.archive([('large.txt', 'a' * 100000)], compression=zipfile.ZIP_DEFLATED))

    def test_crc_corruption(self):
        path = self.archive()
        data = path.read_bytes().replace(b'identifier="manifest"', b'identifier="manifesz"')
        path.write_bytes(data)
        with self.assertRaises(InvalidPackage):
            self.extract(path)

    def test_course_code(self):
        validate_course_code('course-01_test')
        for code in ['../other', '', '/absolute', 'a/b', 'a\r\nDELE x']:
            with self.subTest(code=code), self.assertRaises(InvalidPackage):
                validate_course_code(code)

    def test_upload_limit_and_untrusted_filename(self):
        class Upload:
            filename = '../outside.zip'

            def __init__(self, data):
                self.data = io.BytesIO(data)

            async def read(self, count):
                return self.data.read(count)

        data = self.archive().read_bytes()
        with patch.dict(os.environ, {'SCORM_MAX_UPLOAD_BYTES': '1'}), self.assertRaises(InvalidPackage):
            asyncio.run(prepare_package(Upload(data), self.root))
        root = asyncio.run(prepare_package(Upload(data), self.root))
        self.assertTrue(Path(root).is_dir())
        self.assertFalse((self.root.parent / 'outside.zip').exists())


if __name__ == '__main__':
    unittest.main()
