export const navigation = [
	{ label: "Dashboard", items: [["/", "Home"]] },
	{
		label: "Import Management",
		items: [["/import-files", "Vehicle Import Files", "Vehicle Import File"]],
	},
	{
		label: "Purchasing",
		items: [
			["/suppliers", "Suppliers", "Supplier"],
			["/purchase-orders", "Purchase Orders", "Purchase Order"],
			["/purchase-receipts", "Purchase Receipts", "Purchase Receipt"],
			["/purchase-invoices", "Purchase Invoices", "Purchase Invoice"],
			["/supplier-payments", "Supplier Payments", "Payment Entry"],
			["/landed-costs", "Landed Cost Vouchers", "Landed Cost Voucher"],
		],
	},
	{
		label: "Vehicles",
		items: [
			["/vehicles", "Vehicle Master", "Vehicle Master"],
			["/serials", "VIN and Serial Numbers", "Serial No"],
			["/inspections", "Vehicle Inspections", "Quality Inspection"],
		],
	},
	{
		label: "Sales",
		items: [
			["/customers", "Customers", "Customer"],
			["/quotations", "Quotations", "Quotation"],
			["/sales-orders", "Sales Orders", "Sales Order"],
			["/sales-invoices", "Sales Invoices", "Sales Invoice"],
			["/customer-payments", "Customer Payments", "Payment Entry"],
		],
	},
];
export function recordLocation(record) {
	const base = {
		"Vehicle Master": "/vehicles",
		"Vehicle Import File": "/import-files",
		Customer: "/customers",
		Supplier: "/suppliers",
	}[record.doctype];
	return base
		? { to: `${base}/${encodeURIComponent(record.name)}` }
		: {
				href: `/app/${record.doctype.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(record.name)}`,
			};
}
