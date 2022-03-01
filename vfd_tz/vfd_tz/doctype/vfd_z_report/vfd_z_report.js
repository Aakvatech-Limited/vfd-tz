// Copyright (c) 2021, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on('VFD Z Report', {
	refresh: function (frm) {
		if (frm.doc.sent_status != "Success" && frm.doc.docstatus == 1) {
			frm.add_custom_button('Post To VFD', () => {
				frappe.call({
					method: 'vfd_tz.vfd_tz.doctype.vfd_z_report.vfd_z_report.post',
					args: {
						z_report_name: frm.doc.name
					},
					callback: function (r) {
						if (!r.exc) {
							frappe.msgprint(r.message);
							frm.reload_doc();
						}
					}
				});
			});
		}
	}
});
