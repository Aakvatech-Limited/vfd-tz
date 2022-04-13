// Copyright (c) 2020, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on('VFD Registration', {
	refresh: function (frm) {
		frm.add_custom_button(__('Get new token'), function () {
			frm.trigger("get_new_token");
		});
	},
	get_new_token: function (frm) {
		frappe.call({
			method: 'vfd_tz.vfd_tz.doctype.vfd_token.vfd_token.get_token',
			args: {
				'company': frm.doc.company,
				'force': 1,
			},
			callback: function (r) {
				console.log(r);
			}
		});
	}
});
