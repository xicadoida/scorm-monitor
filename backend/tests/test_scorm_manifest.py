from pathlib import Path
import tempfile
import unittest

from scorm_fixtures import SCORM12, SCORM2004
from scorm_manifest import InvalidManifest, validate_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scormdriver').mkdir()
        (self.root / 'scormdriver/indexAPI.html').write_text('synthetic', encoding='utf-8')

    def validate(self, text):
        (self.root / 'imsmanifest.xml').write_text(text, encoding='utf-8')
        return validate_manifest(self.root)

    def test_manifest_12(self):
        info = self.validate(SCORM12)
        self.assertEqual((info.version, info.launcher), ('1.2', 'scormdriver/indexAPI.html'))

    def test_manifest_2004(self):
        self.assertEqual(self.validate(SCORM2004).version, '2004')

    def test_empty_manifest(self):
        for value in ['', '  \n']:
            with self.subTest(value=value), self.assertRaises(InvalidManifest):
                self.validate(value)

    def test_malformed_xml(self):
        with self.assertRaises(InvalidManifest):
            self.validate('<manifest')

    def test_wrong_structure(self):
        for value in ['<other/>', '<manifest/>', SCORM12.replace('<organizations', '<wrong').replace('</organizations', '</wrong')]:
            with self.subTest(value=value), self.assertRaises(InvalidManifest):
                self.validate(value)

    def test_entities_and_dtd(self):
        for declaration in ['<!DOCTYPE manifest SYSTEM "http://invalid.example/dtd">', '<!DOCTYPE manifest [<!ENTITY secret SYSTEM "file:///never-read">]>']:
            with self.subTest(declaration=declaration), self.assertRaises(InvalidManifest):
                self.validate(SCORM12.replace('<?xml version="1.0"?>', declaration))

    def test_resource_reference(self):
        with self.assertRaises(InvalidManifest):
            self.validate(SCORM12.replace('identifierref="sco"', 'identifierref="missing"'))

    def test_default_organization(self):
        with self.assertRaises(InvalidManifest):
            self.validate(SCORM12.replace('default="org"', 'default="missing"'))

    def test_missing_resource_file(self):
        with self.assertRaises(InvalidManifest):
            self.validate(SCORM12.replace('<file href="scormdriver/indexAPI.html"', '<file href="missing.js"'))

    def test_unsafe_resource_paths(self):
        for href in ['../outside.html', '%2e%2e/outside.html', '/absolute.html', 'file:///private', 'https://external.example/start', 'x\\file.html']:
            with self.subTest(href=href), self.assertRaises(InvalidManifest):
                self.validate(SCORM12.replace('href="scormdriver/indexAPI.html"', f'href="{href}"'))

    def test_launcher_without_driver_folder_and_query(self):
        (self.root / 'start here.html').write_text('ok', encoding='utf-8')
        info = self.validate(SCORM12.replace('scormdriver/indexAPI.html', 'start%20here.html?mode=normal&amp;x=1'))
        self.assertEqual(info.launcher, 'start%20here.html?mode=normal&x=1')

    def test_xml_base_and_group_item(self):
        text = SCORM12.replace('<resource identifier=', '<resource xml:base="scormdriver/" identifier=').replace('scormdriver/indexAPI.html', 'indexAPI.html')
        self.assertEqual(self.validate(text).launcher, 'scormdriver/indexAPI.html')

    def test_manifest_size(self):
        self.validate(SCORM12)
        with self.assertRaises(InvalidManifest):
            validate_manifest(self.root, maximum=1)

    def test_dependency_missing(self):
        with self.assertRaises(InvalidManifest):
            self.validate(SCORM12.replace('</resource>', '<dependency identifierref="absent"/></resource>'))
