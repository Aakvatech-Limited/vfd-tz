import frappe

from vfd_tz.api.utils import get_latest_registration_doc


def execute():
	invoices_list = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "vfd_gc": [">", 0], "vfd_serial": ["in", ["", None]]},
		fields=["name", "company"],
	)
	registrations_dict = frappe._dict()
	for invoice in invoices_list:
		registration_doc: None
		if not registrations_dict.get(invoice.company):
			registration_doc = get_latest_registration_doc(invoice.company)
			registrations_dict[invoice.company] = registration_doc
		else:
			registration_doc = registrations_dict.get(invoice.company)
		if not registration_doc:
			continue
		frappe.db.set_value("Sales Invoice", invoice.name, "vfd_serial", registration_doc.serial)
		print(f"Updated Sales Invoice {invoice.name} with VFD Serial {registration_doc.serial}")
