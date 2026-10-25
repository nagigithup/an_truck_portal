<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import SalesDocumentDialog from "../components/SalesDocumentDialog.vue";
import SupplierPaymentDialog from "../components/SupplierPaymentDialog.vue";
import VehicleDeliveryDialog from "../components/VehicleDeliveryDialog.vue";
import DocumentPrintDialog from "../components/DocumentPrintDialog.vue";
import WarrantyDialog from "../components/WarrantyDialog.vue";

const props = defineProps({ name: String, doctype: String, spareParts: Boolean });
const { notification } = inject("portal");
const state = ref("loading");
const error = ref("");
const result = ref(null);
const nextDialog = ref(null);
const paymentDialog = ref(null);
const deliveryDialog = ref(null);
const printDialog = ref(null);
const warrantyDialog = ref(null);
const salesDocument = computed(() => result.value?.document || {});
const listRoute = computed(() => props.spareParts ? "/spare-parts/sales" : ({
	Quotation: "/quotations",
	"Sales Order": "/sales-orders",
	"Sales Invoice": "/sales-invoices",
})[props.doctype]);

function locale() {
	return globalThis.document?.documentElement?.lang || "en";
}

function amount(value) {
	if (value == null || value === "") return "—";
	try {
		return new Intl.NumberFormat(locale(), {
			style: "currency",
			currency: salesDocument.value.currency || "SAR",
			maximumFractionDigits: 2,
		}).format(Number(value));
	} catch {
		return `${Number(value).toLocaleString()} ${salesDocument.value.currency || ""}`;
	}
}

function date(value) {
	if (!value) return "—";
	try {
		return new Intl.DateTimeFormat(locale(), { dateStyle: "medium" }).format(
			new Date(String(value).replace(" ", "T")),
		);
	} catch {
		return String(value);
	}
}

function status(row) {
	return row.docstatus === 2 ? __("Cancelled") : row.docstatus === 1 ? __(row.status || "Submitted") : __(row.status || "Draft");
}

function routeFor(linked) {
	return {
		Quotation: { name: "quotation-detail", params: { name: linked.name } },
		"Sales Order": { name: "sales-order-detail", params: { name: linked.name } },
		"Sales Invoice": { name: "sales-invoice-detail", params: { name: linked.name } },
		"Payment Entry": { name: "customer-payment-detail", params: { name: linked.name } },
	}[linked.doctype];
}

async function load(silent = false) {
	if (!silent) state.value = "loading";
	error.value = "";
	try {
		const response = await call(props.spareParts ? "an_truck_portal.api.spare_parts_sales.get_invoice" : "an_truck_portal.api.sales.get_sales_document", {
			doctype: props.spareParts ? undefined : props.doctype,
			document: props.name,
		});
		if (!response?.document) throw new Error(__("Unable to load document details."));
		result.value = {
			...response,
			items: Array.isArray(response.items) ? response.items : [],
			attachments: Array.isArray(response.attachments) ? response.attachments : [],
			linked_documents: Array.isArray(response.linked_documents)
				? response.linked_documents
				: [],
			vehicle_deliveries: Array.isArray(response.vehicle_deliveries)
				? response.vehicle_deliveries
				: [],
		};
		state.value = "ready";
	} catch (e) {
		error.value = e?.message || __("Unable to load document details.");
		state.value = "error";
	}
}

async function submitSparePartsInvoice() {
	try {
		await call("an_truck_portal.api.spare_parts_sales.submit_invoice", { document: props.name }, true);
		notification.value = __("Sales Invoice submitted successfully.");
		await load(true);
	} catch (e) {
		error.value = e.message;
	}
}

onMounted(load);
watch([() => props.name, () => props.doctype], () => load());
</script>

<template>
	<div class="page sales-document-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ __(error) }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __(`${doctype} Details`) }}</p>
					<h1><bdi>{{ salesDocument.name }}</bdi></h1>
					<div class="page-actions detail-actions">
						<router-link class="button secondary small" :to="listRoute">{{ __(`Back to ${doctype}s`) }}</router-link>
						<button v-if="spareParts && salesDocument.docstatus === 0 && result.can_submit" type="button" class="button small" @click="submitSparePartsInvoice">{{ __("Submit") }}</button>
						<button v-if="!spareParts && result.can_create_next" type="button" class="button small" @click="nextDialog.open()">{{ __(`+ Create ${result.next_doctype}`) }}</button>
						<button v-if="result.can_record_payment" type="button" class="button small" @click="paymentDialog.open()">{{ __("+ Record Payment") }}</button>
						<button v-if="!spareParts && result.can_deliver_vehicle" type="button" class="button small" @click="deliveryDialog.open()">{{ __("Deliver Vehicle") }}</button>
						<button v-if="!spareParts && doctype === 'Sales Invoice' && result.warranty_context?.vehicles?.length && (result.warranty_context.can_create || result.warranty_context.vehicles.some((row) => row.existing_warranty))" type="button" class="button small" @click="warrantyDialog.open()">{{ __(result.warranty_context.can_create && result.warranty_context.vehicles.some((row) => !row.existing_warranty) ? 'Add Warranty / إضافة ضمان' : 'View Warranty') }}</button>
						<button
							v-else-if="!spareParts && (doctype === 'Sales Order' || doctype === 'Sales Invoice') && salesDocument.docstatus === 1"
							type="button"
							class="button small"
							:aria-label="__('Deliver Vehicle')"
							:title="__(result.delivery_block_reason || '')"
							disabled
						>
							{{ __("Deliver Vehicle") }}
						</button>
						<button type="button" class="button secondary small" @click="printDialog.open()">{{ __("Print") }}</button>
						<a v-if="!spareParts" class="button secondary small" :href="result.desk_url" target="_blank" rel="noopener">{{ __("Open in Desk") }}</a>
					</div>
					<p v-if="result.delivery_block_reason" class="notice compact" role="status">
						{{ __(result.delivery_block_reason) }}
					</p>
				</div>
				<div class="workspace-metrics">
					<div><small>{{ __("Status") }}</small><span class="badge neutral">{{ status(salesDocument) }}</span></div>
					<div><small>{{ __("Customer") }}</small><b>{{ salesDocument.customer_name || salesDocument.customer }}</b></div>
					<div><small>{{ __("Company") }}</small><b>{{ salesDocument.company }}</b></div>
					<div v-if="spareParts"><small>{{ __("Price List") }}</small><b>{{ salesDocument.selling_price_list }}</b></div>
					<div><small>{{ __(salesDocument.posting_date ? "Posting Date" : "Transaction Date") }}</small><b>{{ date(salesDocument.posting_date || salesDocument.transaction_date) }}</b></div>
					<div><small>{{ __(doctype === "Quotation" ? "Valid Till" : doctype === "Sales Order" ? "Delivery Date" : "Due Date") }}</small><b>{{ date(salesDocument.valid_till || salesDocument.delivery_date || salesDocument.due_date) }}</b></div>
					<div><small>{{ __("Grand Total") }}</small><b>{{ amount(salesDocument.grand_total) }}</b></div>
				</div>
			</header>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Items") }}</h2><span class="badge neutral">{{ result.items.length }}</span></div>
				<div class="table-wrap"><table><thead><tr><th>{{ __("Item") }}</th><th>{{ __("Description") }}</th><th>{{ __("Quantity") }}</th><th>{{ __("Rate") }}</th><th>{{ __("Amount") }}</th><th>{{ __("Warehouse") }}</th></tr></thead>
				<tbody><tr v-for="item in result.items" :key="item.name"><td><bdi>{{ item.item_code }}</bdi><small class="table-subtitle">{{ item.item_name }}</small></td><td>{{ item.description || "—" }}</td><td>{{ item.qty }} {{ item.uom }}</td><td>{{ amount(item.rate) }}</td><td>{{ amount(item.amount) }}</td><td>{{ item.warehouse || "—" }}</td></tr></tbody></table></div>
			</section>

			<div class="workspace-grid lower-grid">
				<section class="panel section-card"><div class="section-head"><h2>{{ __("Totals") }}</h2></div><div class="compact-details">
					<div><small>{{ __("Total Quantity") }}</small><b>{{ salesDocument.total_qty }}</b></div><div><small>{{ __("Net Total") }}</small><b>{{ amount(salesDocument.net_total) }}</b></div><div><small>{{ __("Taxes and Charges") }}</small><b>{{ amount(salesDocument.total_taxes_and_charges) }}</b></div><div><small>{{ __("Grand Total") }}</small><b>{{ amount(salesDocument.grand_total) }}</b></div>
					<div v-if="doctype === 'Sales Invoice'"><small>{{ __("Paid Amount") }}</small><b>{{ amount(salesDocument.paid_amount) }}</b></div><div v-if="doctype === 'Sales Invoice'"><small>{{ __("Outstanding Amount") }}</small><b>{{ amount(salesDocument.outstanding_amount) }}</b></div>
				</div></section>
				<section class="panel section-card"><div class="section-head"><h2>{{ __("Attachments") }}</h2></div><div v-if="result.attachments.length" class="document-list"><div v-for="file in result.attachments" :key="file.name"><span>{{ __("Attachment") }}</span><a :href="file.file_url" target="_blank" rel="noopener">{{ file.file_name }}</a></div></div><div v-else class="empty compact">{{ __("No attachments have been added.") }}</div></section>
			</div>

			<section class="panel section-card"><div class="section-head"><h2>{{ __("Linked Documents") }}</h2></div><div v-if="result.linked_documents.length" class="document-list"><div v-for="linked in result.linked_documents" :key="`${linked.doctype}-${linked.name}`"><span>{{ __(linked.doctype) }}</span><router-link v-if="routeFor(linked)" :to="routeFor(linked)"><bdi>{{ linked.name }}</bdi></router-link><bdi v-else>{{ linked.name }}</bdi><small>{{ status(linked) }} · {{ date(linked.date) }}</small></div></div><div v-else class="empty compact">{{ __("No linked documents.") }}</div></section>
			<section v-if="result.vehicle_deliveries.length" class="panel section-card">
				<div class="section-head"><h2>{{ __("Vehicle Deliveries") }}</h2></div>
				<div class="document-list">
					<div v-for="vehicle in result.vehicle_deliveries" :key="vehicle.name">
						<span>{{ __("VIN / Chassis Number") }}</span>
						<bdi>{{ vehicle.chassis_number || vehicle.vin }}</bdi>
						<small>{{ vehicle.delivered ? __("Delivered") : __("Pending Delivery") }}</small>
						<router-link
							v-if="vehicle.delivery_note && vehicle.acknowledgment_available"
							:to="{ name: 'vehicle-delivery-print', params: { name: vehicle.delivery_note } }"
							target="_blank"
						>
							{{ __("View / Print Delivery Note") }}
						</router-link>
					</div>
				</div>
			</section>
			<p v-if="salesDocument.remarks" class="panel section-card detail-notes"><strong>{{ __("Notes") }}:</strong> {{ salesDocument.remarks }}</p>

			<SalesDocumentDialog v-if="result.next_doctype" ref="nextDialog" :doctype="result.next_doctype" :source-name="salesDocument.name" @created="load(true)" />
			<SupplierPaymentDialog v-if="doctype === 'Sales Invoice'" ref="paymentDialog" :sales-invoice="salesDocument.name" @created="load(true)" />
			<VehicleDeliveryDialog
				v-if="doctype === 'Sales Order' || doctype === 'Sales Invoice'"
				ref="deliveryDialog"
				:source-doctype="doctype"
				:source-name="salesDocument.name"
				@confirmed="load(true)"
			/>
			<DocumentPrintDialog ref="printDialog" :doctype="doctype" :document-name="salesDocument.name" />
			<WarrantyDialog v-if="doctype === 'Sales Invoice' && result.warranty_context" ref="warrantyDialog" :sales-invoice="salesDocument.name" :context="result.warranty_context" @created="load(true)" />
		</template>
	</div>
</template>
