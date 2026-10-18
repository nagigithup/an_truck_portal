<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { call, __ } from "../api";
import CreateImportFileDialog from "../components/CreateImportFileDialog.vue";
import PurchaseOrderDialog from "../components/PurchaseOrderDialog.vue";
import PurchaseInvoiceDialog from "../components/PurchaseInvoiceDialog.vue";
import VehicleDrawer from "../components/VehicleDrawer.vue";
import SalesDocumentDialog from "../components/SalesDocumentDialog.vue";
import SupplierPaymentDialog from "../components/SupplierPaymentDialog.vue";

const props = defineProps({ resource: String });
const { ctx } = inject("portal");
const router = useRouter();
const importDialog = ref(null);
const purchaseOrderDialog = ref(null);
const purchaseInvoiceDialog = ref(null);
const vehicleDrawer = ref(null);
const salesDialog = ref(null);
const customerPaymentDialog = ref(null);
const state = ref("loading");
const rows = ref([]);
const search = ref("");
const page = ref(1);
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
		rows.value = (
			await call("an_truck_portal.api.records.list_records", {
				doctype: doctype.value,
				search: search.value,
				company: ctx.company,
				page: page.value,
				filters,
			})
		).rows;
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
		load();
	},
);
let searchTimer;
watch(search, () => {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(load, 300);
});

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
	"purchase_receipt",
	"customer",
	"sales_order",
	"sales_invoice",
	"modified",
	"brand",
	"model",
]);

function vehicleColumns(row) {
	return Object.keys(row).filter(
		(key) =>
			!key.startsWith("_") &&
			(props.resource !== "vehicles" || !hiddenVehicleColumns.has(key)),
	);
}

function columnLabel(key) {
	return __(
		key === "vehicle_import_file"
			? "Vehicle Import File Number"
			: key === "chassis_number"
				? "Chassis Number"
				: key.replaceAll("_", " "),
	);
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
			</div>
			<div class="page-actions">
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
		<div class="panel table-wrap">
			<div v-if="state === 'loading'" class="empty">{{ __("Loading…") }}</div>
			<div v-else-if="state === 'error'" class="empty error">{{ rows[0]?.error }}</div>
			<div v-else-if="!rows.length" class="empty">{{ __("No records found") }}</div>
			<table v-else>
				<thead>
					<tr>
						<th v-for="key in vehicleColumns(rows[0])" :key="key">
							{{ columnLabel(key) }}
						</th>
						<th v-if="resource === 'vehicles'">{{ __("Actions") }}</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in rows" :key="row.name" @click="resource === 'vehicles' ? undefined : open(row)">
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
		<CreateImportFileDialog v-if="resource === 'import-files'" ref="importDialog" />
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
