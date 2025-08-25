import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    customer_fields = {
        "Customer": [
            {
                "label": "VFD Customer ID",
                "fieldname": "vfd_cust_id",
                "fieldtype": "Data",
                "insert_after": "vfd_details",
                "no_copy": 1,
                "translatable": 1,
                "module_def": "vfd-tz",
            },
            {
                "fieldname": "vfd_details",
                "insert_after": "tax_withholding_category",
            },
            {
                "label": "VFD Customer ID Type",
                "fieldname": "vfd_cust_id_type",
                "fieldtype": "Select",
                "options": "\n1- TIN\n2- Driving License\n3- Voters Number\n4- Passport\n5- NID (National Identity)\n6- Other",
                "insert_after": "vfd_cust_id",
                "no_copy": 1,
                "translatable": 1,
                "module_def": "vfd-tz",
            },
        ],
        "Sales Invoice": [
            {
                "fieldname": "vfd_cust_id",
                "fetch_from": "customer.vfd_cust_id",
            },
            {
                "fieldname": "vfd_cust_id_type",
                "fetch_from": "customer.vfd_cust_id_type",
            },
        ],
    }

    create_custom_fields(customer_fields, update=True)


