frappe.ui.form.on("Sales Invoice", {
  onload: function (frm) {
    frm.trigger("make_vfd_btn");
  },
  refresh: function (frm) {
    frm.trigger("make_vfd_btn");
  },
  make_vfd_btn: function (frm) {
    if (
      frm.doc.docstatus == 1 &&
      frm.doc.vfd_status != "Success" &&
      !frm.doc.is_return
    ) {
      frm.add_custom_button(__("Generate VFD"), function () {
        if (!frm.doc.vfd_cust_id) {
          frappe.msgprint({
            title: __("Confirmation Required"),
            message: __("Are you sure you want to send VFD without TIN"),
            primary_action: {
              label: "Proceed",
              action(values) {
                generate_vfd(frm);
                cur_dialog.cancel();
              },
            },
          });
        } else if (
          frm.doc.vfd_cust_id &&
          frm.doc.vfd_cust_id != frm.doc.tax_id
        ) {
          frappe.msgprint({
            title: __("Confirmation Required"),
            message: __("TIN an VFD Customer ID mismatch"),
            primary_action: {
              label: "Proceed",
              action(values) {
                generate_vfd(frm);
                cur_dialog.cancel();
              },
            },
          });
        } else {
          generate_vfd(frm);
        }
      });
    }
  },
});

function generate_vfd(frm) {
  frappe.dom.freeze(__("Generating VFD..."));
  frappe.call({
    method: "vfd_tz.vfd_tz.api.sales_invoice.enqueue_posting_vfd_invoice",
    args: {
      invoice_name: frm.doc.name,
    },
    callback: function (r) {
      if (!r.exc) {
        frm.reload_doc();
        frappe.show_alert({
          message: __("VFD Generated"),
          indicator: "green",
        });
      } else {
        frappe.msgprint(__("Error generating VFD"));
      }
      frappe.dom.unfreeze();
    },
  });
}
