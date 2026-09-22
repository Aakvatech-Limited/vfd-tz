"""Certificate attachments must resolve inside the site directory."""

import frappe
from frappe.tests import IntegrationTestCase

from vfd_tz.api.utils import get_absolute_path


class TestCertificatePathResolution(IntegrationTestCase):
	def _site_files(self, folder):
		return f"{frappe.utils.get_bench_path()}/sites/{frappe.local.site}/{folder}/files"

	def test_public_attachment_resolves_inside_the_site_directory(self):
		self.assertEqual(get_absolute_path("/files/cert.pfx"), f"{self._site_files('public')}/cert.pfx")

	def test_private_attachment_resolves_inside_the_site_directory(self):
		self.assertEqual(
			get_absolute_path("/private/files/cert.pfx"),
			f"{self._site_files('private')}/cert.pfx",
		)

	def test_a_bare_file_name_resolves_to_the_public_folder(self):
		self.assertEqual(get_absolute_path("cert.pfx"), f"{self._site_files('public')}/cert.pfx")
