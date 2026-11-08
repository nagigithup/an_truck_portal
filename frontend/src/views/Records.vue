<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { call, downloadFile, __ } from "../api";
import { language } from "../i18n";
import CreateImportFileDialog from "../components/CreateImportFileDialog.vue";
import PurchaseOrderDialog from "../components/PurchaseOrderDialog.vue";
import PurchaseInvoiceDialog from "../components/PurchaseInvoiceDialog.vue";
import VehicleDrawer from "../components/VehicleDrawer.vue";
import SalesDocumentDialog from "../components/SalesDocumentDialog.vue";
import SupplierPaymentDialog from "../components/SupplierPaymentDialog.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import ImportFileExcelDialog from "../components/ImportFileExcelDialog.vue";

const props = defineProps({ resource: String });
const { ctx } = inject("portal");
const router = useRouter();
const importDialog = ref(null);
const excelDialog=ref(null),exporting=ref(false),excelError=ref("");
const purchaseOrderDialog = ref(null);
const purchaseInvoiceDialog = ref(null);
const vehicleDrawer = ref(null);
const salesDialog = ref(null);
const customerPaymentDialog = ref(null);
const state = ref("loading");
const rows = ref([]);
const search = ref("");
const page = ref(1);
const pageLength = ref(20);
const total = ref(0);
const vehicleStatusOptions = ref([]);
const chassisFilter = ref("");
const itemNameFilter = ref("");
const vehicleStatusFilter = ref("");
const doctypes = {
	"import-files": "Vehicle Import File",
	vehicles: "Vehicle Master",
	suppliers: "Supplier",
	"purchase-orders": "Purchase Order",
	"purchase-receipts": "Purchase Receipt",
	"purchase-invoices": "Purchase Invoice",
	"supplier-payments": "Payment Entry",
	"landed-costs": "Landed Cost Voucher",
	customers: "Customer",
	quotations: "Quotation",
	"sales-orders": "Sales Order",
	"sales-invoices": "Sales Invoice",
	"customer-payments": "Payment Entry",
	serials: "Serial No",
	inspections: "Quality Inspection",
};
const doctype = computed(() => doctypes[props.resource]);

async function load() {
	state.value = "loading";
	try {
		const filters =
			props.resource === "supplier-payments"
				? { payment_type: "Pay", party_type: "Supplier" }
				: props.resource === "customer-payments"
					? { payment_type: "Receive", party_type: "Customer" }
					: {};
		const result = await call("an_truck_portal.api.records.list_records", {
				doctype: doctype.value,
				search: search.value,
				company: ctx.company,
				page: page.value,
				filters,
				column_filters:
					props.resource === "vehicles"
						? {
							chassis_number: chassisFilter.value,
							item_name: itemNameFilter.value,
							vehicle_status: vehicleStatusFilter.value,
						}
						: {},
			});
		rows.value = result.rows;
		total.value = result.total ?? result.rows.length;
		pageLength.value = result.page_length || 20;
		vehicleStatusOptions.value = result.filter_options?.vehicle_status || [];
		state.value = "ready";
	} catch (e) {
		state.value = "error";
		rows.value = [{ error: e.message }];
	}
}

onMounted(load);
watch(
	() => props.resource,
	() => {
		page.value = 1;
		chassisFilter.value = "";
		itemNameFilter.value = "";
		vehicleStatusFilter.value = "";
		load();
	},
);
let searchTimer;
watch([search, chassisFilter, itemNameFilter, vehicleStatusFilter], () => {
	page.value = 1;
	clearTimeout(searchTimer);
	searchTimer = setTimeout(load, 300);
});

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageLength.value)));

function open(row) {
	if (doctype.value === "Vehicle Import File") {
		router.push({ name: "import-workspace", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Vehicle Master") {
		router.push({ name: "detail", params: { resource: "vehicles", name: row.name } });
		return;
	}
	if (doctype.value === "Purchase Order") {
		router.push({ name: "purchase-order-detail", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Purchase Invoice") {
		router.push({ name: "purchase-invoice-detail", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Purchase Receipt") {
		router.push({ name: "purchase-receipt-detail", params: { name: row.name } });
		return;
	}
	if (props.resource === "supplier-payments") {
		router.push({ name: "supplier-payment-detail", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Landed Cost Voucher") {
		router.push({ name: "landed-cost-detail", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Quotation") {
		router.push({ name: "quotation-detail", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Sales Order") {
		router.push({ name: "sales-order-detail", params: { name: row.name } });
		return;
	}
	if (doctype.value === "Sales Invoice") {
		router.push({ name: "sales-invoice-detail", params: { name: row.name } });
		return;
	}
	if (props.resource === "customer-payments") {
		router.push({ name: "customer-payment-detail", params: { name: row.name } });
		return;
	}
	window.location.href = `/app/${doctype.value.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(row.name)}`;
}

async function purchaseOrderCreated(result) {
	await load();
	router.push({ name: "purchase-order-detail", params: { name: result.name } });
}

async function purchaseInvoiceCreated(result) {
	await load();
	router.push({ name: "purchase-invoice-detail", params: { name: result.name } });
}

const hiddenVehicleColumns = new Set([
	"name",
	"vin",
	"company",
	"item_code",
	"vehicle_import_file",
	"purchase_receipt",
	"customer",
	"sales_order",
	"sales_invoice",
	"modified",
	"brand",
	"model",
]);

const importFileColumns = {
	name: "Name",
	supplier: "Supplier",
	received_vehicles: "Received Vehicles",
	sold_vehicles: "Sold Vehicles",
	remaining_vehicles: "Remaining Vehicles",
	purchase_value_invoice_currency: "Purchase Value (Invoice Currency)",
	paid_amount_invoice_currency: "Paid Amount (Invoice Currency)",
	outstanding_amount_invoice_currency: "Outstanding Amount (Invoice Currency)",
	status: "Status",
	country_of_origin: "Country of Origin",
	supplier_currency: "Supplier Currency",
	purchase_value_sar: "Purchase Value (SAR)",
	paid_amount_sar: "Paid Amount (SAR)",
	outstanding_amount_sar: "Outstanding Amount (SAR)",
};

function vehicleColumns(row = {}) {
	if (props.resource === "import-files") return Object.keys(importFileColumns);
	if (props.resource === "vehicles" && !Object.keys(row).length) {
		return ["chassis_number", "item_name", "vehicle_status"];
	}
	return Object.keys(row).filter(
		(key) =>
			!key.startsWith("_") &&
			(props.resource !== "vehicles" || !hiddenVehicleColumns.has(key)),
	);
}

function columnLabel(key) {
	if (props.resource === "import-files") return __(importFileColumns[key]);
	return __(
		{
			vehicle_import_file: "Vehicle Import File Number",
			chassis_number: "Chassis Number",
			item_name: "Item Name",
			vehicle_status: "Vehicle Status",
			warranty: "Warranty Expiry Date",
		}[key] || key.replaceAll("_", " "),
	);
}

function purchaseAmount(value) {
	try {
		return new Intl.NumberFormat(language.value, {
			style: "currency", currency: value.currency, currencyDisplay: "code",
		}).format(value.amount);
	} catch {
		return `${new Intl.NumberFormat(language.value).format(value.amount)} ${value.currency || ""}`.trim();
	}
}

async function exportExcel(){
	if(exporting.value)return;
	exporting.value=true;excelError.value='';
	try{await downloadFile('an_truck_portal.api.import_file_excel.export',{company:ctx.company,search:search.value},'import-files.xlsx');}
	catch(e){excelError.value=e.message;}finally{exporting.value=false;}
}

function openVehicle(vehicle, edit = false) {
	vehicleDrawer.value?.open(vehicle, edit);
}

async function vehicleSaved() {
	await load();
}

async function salesCreated(result) {
	await load();
	router.push({
		name: {
			Quotation: "quotation-detail",
			"Sales Order": "sales-order-detail",
			"Sales Invoice": "sales-invoice-detail",
		}[result.doctype],
		params: { name: result.name },
	});
}

async function customerPaymentCreated(result) {
	await load();
	router.push({ name: "customer-payment-detail", params: { name: result.name } });
}
</script>

<template>
	<div class="page">
		<div class="page-head">
			<div>
				<p class="eyebrow">{{ __("Records") }}</p>
				<h1>{{ __(doctype) }}</h1>
				<small v-if="resource === 'import-files'">{{ __('Financial amounts use submitted purchase invoices and recorded allocations. Invoice currencies are shown separately; SAR equivalents use recorded accounting conversions.') }}</small>
				<p v-if="resource === 'vehicles'" class="records-total">{{ __("Number of Vehicles") }}: <b>{{ total }}</b></p>
			</div>
			<div class="page-actions">
				<button v-if="resource==='import-files' && ctx.permissions['Vehicle Import File']?.create" type="button" class="button secondary" @click="excelDialog.open()">{{ __('Import Excel') }}</button>
				<button v-if="resource==='import-files' && ctx.permissions['Vehicle Import File']?.export" type="button" class="button secondary" :disabled="exporting" @click="exportExcel">{{ __('Export Excel') }}</button>
				<button
					v-if="
						resource === 'import-files' &&
						ctx.permissions['Vehicle Import File']?.create
					"
					type="button"
					class="button"
					@click="importDialog.open()"
				>
					{{ __("+ Create Vehicle File") }}
				</button>
				<button
					v-if="resource === 'purchase-orders' && ctx.permissions['Purchase Order']?.create"
					type="button"
					class="button"
					@click="purchaseOrderDialog.open()"
				>
					{{ __("+ Create Purchase Order") }}
				</button>
				<button
					v-if="resource === 'purchase-invoices' && ctx.permissions['Purchase Invoice']?.create"
					type="button"
					class="button"
					@click="purchaseInvoiceDialog.open()"
				>
					{{ __("+ Create Purchase Invoice") }}
				</button>
				<button
					v-if="['quotations', 'sales-orders', 'sales-invoices'].includes(resource) && ctx.permissions[doctype]?.create"
					type="button"
					class="button"
					@click="salesDialog.open()"
				>
					{{ __(`+ Create ${doctype}`) }}
				</button>
				<button
					v-if="resource === 'customer-payments' && ctx.permissions['Payment Entry']?.create"
					type="button"
					class="button"
					@click="customerPaymentDialog.open()"
				>
					{{ __("+ Record Payment") }}
				</button>
				<input v-model="search" class="filter" :placeholder="__('Search…')" />
			</div>
		</div>
		<p v-if="excelError" class="notice error-notice">{{ excelError }}</p>
		<FilterBar v-if="resource === 'vehicles'" class="panel vehicle-filters">
			<FormField v-model="chassisFilter" :label="__('Chassis Number')" ltr />
			<FormField v-model="itemNameFilter" :label="__('Item Name')" />
			<div class="form-field">
				<label for="vehicle-status-filter">{{ __("Vehicle Status") }}</label>
				<select id="vehicle-status-filter" v-model="vehicleStatusFilter">
					<option value="">{{ __("All statuses") }}</option>
					<option v-for="status in vehicleStatusOptions" :key="status" :value="status">{{ __(status) }}</option>
				</select>
			</div>
		</FilterBar>
		<div class="panel table-wrap">
			<div v-if="state === 'loading'" class="empty">{{ __("Loading…") }}</div>
			<div v-else-if="state === 'error'" class="empty error">{{ rows[0]?.error }}</div>
			<div v-else-if="!rows.length && !['vehicles', 'import-files'].includes(resource)" class="empty">{{ __("No records found") }}</div>
			<table v-else>
				<thead>
					<tr>
						<th v-if="resource === 'vehicles'">{{ __("No.") }}</th>
						<th v-for="key in vehicleColumns(rows[0] || {})" :key="key">
							{{ columnLabel(key) }}
						</th>
						<th v-if="resource === 'vehicles'">{{ __("Actions") }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-if="['vehicles', 'import-files'].includes(resource) && !rows.length"><td :colspan="vehicleColumns({}).length + (resource === 'vehicles' ? 2 : 0)" class="empty">{{ __("No records found") }}</td></tr>
					<tr v-for="(row, index) in rows" :key="row.name" @click="resource === 'vehicles' ? undefined : open(row)">
						<td v-if="resource === 'vehicles'" class="record-number">{{ (page - 1) * pageLength + index + 1 }}</td>
						<td
							v-for="key in vehicleColumns(row)"
							:key="key"
							:class="{ ltr: key === 'chassis_number' }"
						>
							<button
								v-if="resource === 'vehicles' && key === 'chassis_number'"
								type="button"
								class="link-button ltr"
								@click.stop="openVehicle(row)"
							>
								{{ row[key] || "—" }}
							</button>
							<router-link
								v-else-if="resource === 'vehicles' && key === 'vehicle_import_file' && row[key]"
								:to="{ name: 'import-workspace', params: { name: row[key] } }"
								@click.stop
							>
								<bdi>{{ row[key] }}</bdi>
							</router-link>
							<bdi v-else-if="resource === 'vehicles' && key === 'warranty'">{{ row.warranty?.expiry_date || "—" }}</bdi>
							<span v-else-if="resource === 'import-files' && ['received_vehicles','sold_vehicles','remaining_vehicles'].includes(key)" :title="__(row._vehicle_issue || '')">{{ row[key] ?? "—" }}</span>
							<div v-else-if="resource === 'import-files' && /^(purchase_value|paid_amount|outstanding_amount)_/.test(key)" class="purchase-values" :title="__(key.endsWith('_sar') ? row._sar_finance_issue || '' : row._invoice_finance_issue || '')">
								<small v-if="key === 'purchase_value_invoice_currency' && row[key]?.length > 1">{{ __('Mixed Invoice Currencies') }}</small>
								<bdi v-for="value in row[key] || []" :key="value.currency">{{ purchaseAmount(value) }}</bdi>
								<span v-if="!row[key]?.length">{{ row[key] == null ? "—" : "0" }}</span>
							</div>
							<span v-else-if="key === 'status' || key === 'vehicle_status'" class="badge">
								{{ __(row[key]) }}
							</span>
							<template v-else>{{ row[key] ?? "—" }}</template>
						</td>
						<td v-if="resource === 'vehicles'" class="row-actions">
							<button type="button" class="text-button" @click.stop="openVehicle(row)">{{ __("View") }}</button>
							<button v-if="row._can_edit" type="button" class="text-button" @click.stop="openVehicle(row, true)">{{ __("Edit") }}</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-if="['vehicles', 'import-files'].includes(resource) && state === 'ready' && total" class="pagination">
			<span>{{ __("Page") }} {{ page }} / {{ totalPages }}<template v-if="resource === 'vehicles'"> · {{ __("Number of Vehicles") }}: {{ total }}</template></span>
			<div class="row-actions"><button class="button secondary" :disabled="page === 1" @click="page--; load()">{{ __("Previous") }}</button><button class="button secondary" :disabled="page >= totalPages" @click="page++; load()">{{ __("Next") }}</button></div>
		</div>
		<CreateImportFileDialog v-if="resource === 'import-files'" ref="importDialog" />
		<ImportFileExcelDialog v-if="resource === 'import-files'" ref="excelDialog" @imported="load" />
		<PurchaseOrderDialog
			v-if="resource === 'purchase-orders'"
			ref="purchaseOrderDialog"
			@created="purchaseOrderCreated"
		/>
		<PurchaseInvoiceDialog
			v-if="resource === 'purchase-invoices'"
			ref="purchaseInvoiceDialog"
			@created="purchaseInvoiceCreated"
		/>
		<VehicleDrawer v-if="resource === 'vehicles'" ref="vehicleDrawer" @saved="vehicleSaved" />
		<SalesDocumentDialog
			v-if="['quotations', 'sales-orders', 'sales-invoices'].includes(resource)"
			ref="salesDialog"
			:doctype="doctype"
			@created="salesCreated"
		/>
		<SupplierPaymentDialog
			v-if="resource === 'customer-payments'"
			ref="customerPaymentDialog"
			@created="customerPaymentCreated"
		/>
	</div>
</template>

<style scoped>
.vehicle-filters { margin-bottom: 16px; }
.purchase-values { display: flex; flex-direction: column; gap: 3px; }
.purchase-values bdi { white-space: nowrap; }
</style>
