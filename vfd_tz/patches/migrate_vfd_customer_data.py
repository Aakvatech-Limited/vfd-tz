import frappe


BATCH_SIZE = 5000


def execute():
    if not (
        frappe.db.has_column("Customer", "vfd_cust_id_type")
        and frappe.db.has_column("Customer", "vfd_cust_id")
    ):
        return

    filters = [
        ["vfd_custidtype", "not in", (None, "")],
        ["vfd_custid", "not in", (None, "")],
    ]

    start = 0
    while True:
        customers = frappe.get_all(
            "Customer",
            fields=["name", "vfd_custidtype", "vfd_custid"],
            filters=filters,
            limit_start=start,
            limit_page_length=BATCH_SIZE,
            order_by="creation desc",
        )
        if not customers:
            break

        for customer in customers:
            frappe.db.set_value(
                "Customer",
                customer.name,
                {
                    "vfd_cust_id_type": customer.vfd_custidtype,
                    "vfd_cust_id": customer.vfd_custid,
                },
                update_modified=False,
            )

        frappe.db.commit()
        start += BATCH_SIZE


def delete():
    for fieldname in ("vfd_custidtype", "vfd_custid"):
        custom_field_name = f"Customer-{fieldname}"
        if frappe.db.exists("Custom Field", custom_field_name):
            frappe.delete_doc("Custom Field", custom_field_name)

    frappe.db.commit()