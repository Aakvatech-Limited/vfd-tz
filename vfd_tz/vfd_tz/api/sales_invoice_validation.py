import frappe

from vfd_tz.vfd_tz.api.sales_invoice import vfd_validation as _vfd_validation


def _get_calculated_item_wise_tax_details(doc):
	details = []

	for row in doc.get("_item_wise_tax_details") or []:
		item = row.get("item")
		tax = row.get("tax")

		if not item or not tax:
			continue

		details.append(
			frappe._dict(
				{
					"item_row": item.name,
					"tax_row": tax.name,
					"rate": row.get("rate"),
					"amount": row.get("amount"),
					"taxable_amount": row.get("taxable_amount"),
				}
			)
		)

	return details


def vfd_validation(doc, method=None):
	"""Validate VFD taxes using the tax details available at before_submit.

	ERPNext calculates item-wise taxes into ``_item_wise_tax_details`` during
	validation and only materializes ``item_wise_tax_details`` in ``on_update``.
	The VFD hook runs in ``before_submit``, so temporarily expose the calculated
	rows in the persisted-table shape expected by the existing VFD validation.
	"""
	calculated_details = _get_calculated_item_wise_tax_details(doc)
	if not calculated_details:
		return _vfd_validation(doc, method)

	original_details = doc.get("item_wise_tax_details") or []
	doc.set("item_wise_tax_details", calculated_details)

	try:
		return _vfd_validation(doc, method)
	finally:
		doc.set("item_wise_tax_details", original_details)
