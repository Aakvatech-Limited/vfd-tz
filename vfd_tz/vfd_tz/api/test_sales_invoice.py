import json

import frappe
from frappe.tests.utils import FrappeTestCase

from vfd_tz.vfd_tz.api.sales_invoice import (
    get_itemised_tax_breakup_data,
    get_itemised_tax_from_details,
)


class TestSalesInvoiceTaxBreakup(FrappeTestCase):
    def _make_tax_doc(self, rate=18, amount=180):
        return frappe._dict(
            items=[
                frappe._dict(
                    name="ITEM-ROW-1",
                    item_code="TEST-ITEM-1",
                )
            ],
            taxes=[
                frappe._dict(
                    name="TAX-ROW-1",
                    description="VAT 18%",
                    account_head="VAT - TEST",
                    category="Total",
                )
            ],
            item_wise_tax_details=[
                frappe._dict(
                    item_row="ITEM-ROW-1",
                    tax_row="TAX-ROW-1",
                    rate=rate,
                    amount=amount,
                )
            ],
        )

    def test_item_wise_tax_details_are_mapped_to_item_code(self):
        doc = self._make_tax_doc()

        tax_data = get_itemised_tax_breakup_data(doc)

        self.assertIn("TEST-ITEM-1", tax_data)
        self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_rate, 18)
        self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_amount, 180)

    def test_tax_account_can_be_included(self):
        doc = self._make_tax_doc()

        tax_data = get_itemised_tax_from_details(doc, with_tax_account=True)

        self.assertEqual(
            tax_data["TEST-ITEM-1"]["VAT 18%"].tax_account,
            "VAT - TEST",
        )

    def test_legacy_json_item_wise_tax_detail_fallback_is_preserved(self):
        doc = frappe._dict(
            items=[],
            item_wise_tax_details=[],
            taxes=[
                frappe._dict(
                    name="TAX-ROW-1",
                    description="VAT 18%",
                    account_head="VAT - TEST",
                    category="Total",
                    item_wise_tax_detail=json.dumps(
                        {"TEST-ITEM-1": [18, 180]}
                    ),
                )
            ],
        )

        tax_data = get_itemised_tax_breakup_data(doc)

        self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_rate, 18)
        self.assertEqual(tax_data["TEST-ITEM-1"]["VAT 18%"].tax_amount, 180)
