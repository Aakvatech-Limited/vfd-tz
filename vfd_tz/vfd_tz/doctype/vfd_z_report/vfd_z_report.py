# Copyright (c) 2021, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from csf_tz import console


class VFDZReport(Document):
    def validate(self):
        self.set_data()

    def before_submit(self):
        pass

    def on_submit(self):
        pass

    def set_data(self):
        company = frappe.get_value("VFD Registration", self.vfd_registration, "company")
        z_last_gc = get_z_last_gc(self.vfd_registration)
        self.vfd_gc_previous = z_last_gc
        invoices = get_invoices(company, z_last_gc)
        if len(invoices) > 0:
            self.vfd_gc_from = z_last_gc + 1
            self.vfd_gc_to = get_invoices_last_gc(company)
            self.set_inovices(invoices)
        else:
            self.vfd_gc_from = None
            self.vfd_gc_to = None
        console(invoices)

    def set_inovices(self, invoices):
        self.invoices = []
        if len(invoices) == 0:
            return
        for el in invoices:
            row = self.append("invoices", {})
            row.invoice = el.name
            row.vfd_gc = el.vfd_gc


def get_z_last_gc(vfd_registration):
    report_list = frappe.db.sql(
        """
    SELECT MAX(vfd_gc_previous) as gc
    FROM `tabVFD Z Report`
    WHERE 
        vfd_registration = '{0}'
        and docstatus = 1
    """.format(
            vfd_registration
        ),
        as_dict=True,
    )
    if len(report_list) > 0 and report_list[0].get("gc"):
        return report_list[0].get("gc")
    else:
        return 0


def get_invoices_last_gc(company):
    invoices_list = frappe.db.sql(
        """
    SELECT MAX(vfd_gc) as gc
    FROM `tabSales Invoice`
    WHERE 
        company = '{0}'
        and docstatus = 1
    """.format(
            company
        ),
        as_dict=True,
    )
    if len(invoices_list) > 0 and invoices_list[0].get("gc"):
        return invoices_list[0].get("gc")
    else:
        return None


def get_invoices(company, last_gc):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"company": company, "docstatus": 1, "vfd_gc": [">", last_gc]},
        fields=["*"],
        order_by="vfd_gc",
    )
    return invoices
