export const navigation = [
	{
		label: "Import Management",
		hideLabel: true,
		items: [
			["/import-files", "Vehicle Import Files", "Vehicle Import File"],
			["/vehicles", "Vehicle Master", "Vehicle Master"],
		],
	},
	{
		label: "Purchasing",
		items: [
			["/suppliers", "Suppliers", "Supplier"],
			["/purchase-orders", "Purchase Orders", "Purchase Order"],
			["/purchase-receipts", "Purchase Receipts", "Purchase Receipt"],
			["/purchase-invoices", "Purchase Invoices", "Purchase Invoice"],
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
	{
		label: "Sales Management",
		items: [
			["/spare-parts/items", "Spare Parts Items", "Item"],
			["/spare-parts/stock", "Spare Parts Stock", "Bin"],
			["/spare-parts/sales", "Spare Parts Sales", "Sales Invoice"],
			["/maintenance-centers", "Maintenance Centers", "Warranty Provider"],
		],
	},
	{
		label: "Warranty",
		items: [
			["/warranty-dashboard", "Warranty Dashboard", "Warranty Claim"],
			["/warranties", "Vehicle Warranties", "Vehicle Warranty"],
			["/warranty-claims", "Warranty Claims", "Warranty Claim"],
			["/warranty/providers", "Warranty Providers", "Warranty Provider"],
			["/warranty/provider-contracts", "Provider Contracts", "Warranty Provider Contract"],
			["/warranty/coverage-templates", "Coverage Templates", "Warranty Coverage Template"],
			["/warranty/coverage-categories", "Coverage Categories", "Warranty Coverage Category"],
		],
	},
];
export function recordLocation(record) {
	if (
		record.doctype === "Payment Entry" &&
		record.payment_type === "Pay" &&
		record.party_type === "Supplier"
	) {
		return { to: `/supplier-payments/${encodeURIComponent(record.name)}` };
	}
	const base = {
		"Vehicle Master": "/vehicles",
		"Vehicle Import File": "/import-files",
		"Purchase Order": "/purchase-orders",
		"Purchase Invoice": "/purchase-invoices",
		"Purchase Receipt": "/purchase-receipts",
		"Landed Cost Voucher": "/landed-costs",
		Customer: "/customers",
		Supplier: "/suppliers",
	}[record.doctype];
	return base
		? { to: `${base}/${encodeURIComponent(record.name)}` }
		: {
				href: `/app/${record.doctype.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(record.name)}`,
			};
}
