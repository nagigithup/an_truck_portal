<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import SupplierPaymentDialog from "../components/SupplierPaymentDialog.vue";

const props = defineProps({ name: String });
const state = ref("loading");
const error = ref("");
const result = ref(null);
const paymentDialog = ref(null);
const invoice = computed(() => result.value?.purchase_invoice || {});

function amount(value) {
	if (value == null || value === "") return "—";
	try {
		return new Intl.NumberFormat(document.documentElement.lang, {
			style: "currency",
			currency: invoice.value.currency || "SAR",
			maximumFractionDigits: 2,
		}).format(Number(value));
	} catch {
		return `${Number(value).toLocaleString()} ${invoice.value.currency || ""}`;
	}
}

function date(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat(document.documentElement.lang, { dateStyle: "medium" }).format(
		new Date(String(value).replace(" ", "T")),
	);
}

function documentStatus(row) {
	return row.docstatus === 2
		? __("Cancelled")
		: row.docstatus === 1
			? __(row.status || "Submitted")
			: __(row.status || "Draft");
}

function documentRoute(document) {
	if (document.doctype === "Purchase Order") {
		return { name: "purchase-order-detail", params: { name: document.name } };
	}
	if (document.doctype === "Purchase Receipt") {
		return { name: "purchase-receipt-detail", params: { name: document.name } };
	}
	if (document.doctype === "Payment Entry") {
		return { name: "supplier-payment-detail", params: { name: document.name } };
	}
	return null;
}

async function load(silent = false) {
	if (!silent) state.value = "loading";
	error.value = "";
	try {
		result.value = await call("an_truck_portal.api.import_file.get_purchase_invoice", {
			purchase_invoice: props.name,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}

async function paymentCreated() {
	await load(true);
}

onMounted(load);
watch(() => props.name, () => load());
</script>

<template>
	<div class="page purchase-invoice-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __("Purchase Invoice Details") }}</p>
					<h1><bdi>{{ invoice.name }}</bdi></h1>
					<div class="page-actions detail-actions">
						<router-link v-if="invoice.vehicle_import_file" :to="{ name: 'import-workspace', params: { name: invoice.vehicle_import_file } }">
							{{ __("Vehicle Import File") }}: <bdi>{{ invoice.vehicle_import_file }}</bdi>
						</router-link>
						<button v-if="invoice.can_record_payment" type="button" class="button small" @click="paymentDialog.open()">{{ __("+ Record Payment") }}</button>
					</div>
				</div>
				<div class="workspace-metrics">
					<div><small>{{ __("Status") }}</small><span class="badge neutral">{{ documentStatus(invoice) }}</span></div>
					<div><small>{{ __("Supplier") }}</small><b>{{ invoice.supplier_name || invoice.supplier }}</b></div>
					<div><small>{{ __("Company") }}</small><b>{{ invoice.company }}</b></div>
					<div><small>{{ __("Posting Date") }}</small><b>{{ date(invoice.posting_date) }}</b></div>
					<div><small>{{ __("Due Date") }}</small><b>{{ date(invoice.due_date) }}</b></div>
					<div><small>{{ __("Grand Total") }}</small><b>{{ amount(invoice.grand_total) }}</b></div>
				</div>
			</header>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Items") }}</h2><span class="badge neutral">{{ result.items.length }}</span></div>
				<div class="table-wrap"><table>
					<thead><tr><th>{{ __("Item") }}</th><th>{{ __("Description") }}</th><th>{{ __("Quantity") }}</th><th>{{ __("Rate") }}</th><th>{{ __("Amount") }}</th><th>{{ __("Purchase Order") }}</th><th>{{ __("Purchase Receipt") }}</th></tr></thead>
					<tbody><tr v-for="item in result.items" :key="item.name">
						<td><bdi>{{ item.item_code }}</bdi><small class="table-subtitle">{{ item.item_name }}</small></td><td>{{ item.description || "—" }}</td><td>{{ item.qty }} {{ item.uom }}</td><td>{{ amount(item.rate) }}</td><td>{{ amount(item.amount) }}</td>
						<td><router-link v-if="item.purchase_order" :to="{ name: 'purchase-order-detail', params: { name: item.purchase_order } }"><bdi>{{ item.purchase_order }}</bdi></router-link><span v-else>—</span></td><td><router-link v-if="item.purchase_receipt" :to="{ name: 'purchase-receipt-detail', params: { name: item.purchase_receipt } }"><bdi>{{ item.purchase_receipt }}</bdi></router-link><span v-else>—</span></td>
					</tr></tbody>
				</table></div>
			</section>

			<div class="workspace-grid lower-grid">
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Totals") }}</h2></div>
					<div class="compact-details">
						<div><small>{{ __("Total Quantity") }}</small><b>{{ invoice.total_qty }}</b></div><div><small>{{ __("Net Total") }}</small><b>{{ amount(invoice.net_total) }}</b></div>
						<div><small>{{ __("Taxes and Charges") }}</small><b>{{ amount(invoice.total_taxes_and_charges) }}</b></div><div><small>{{ __("Grand Total") }}</small><b>{{ amount(invoice.grand_total) }}</b></div>
					</div>
				</section>
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Payment Status") }}</h2></div>
					<div class="compact-details">
						<div><small>{{ __("Status") }}</small><b>{{ documentStatus(invoice) }}</b></div><div><small>{{ __("Paid Amount") }}</small><b>{{ amount(invoice.paid_amount) }}</b></div><div><small>{{ __("Outstanding Amount") }}</small><b>{{ amount(invoice.outstanding_amount) }}</b></div>
						<div><small>{{ __("Supplier Invoice Number") }}</small><b>{{ invoice.bill_no || "—" }}</b></div><div><small>{{ __("Supplier Invoice Date") }}</small><b>{{ date(invoice.bill_date) }}</b></div>
					</div>
				</section>
			</div>

			<div class="workspace-grid lower-grid">
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Attachments") }}</h2></div>
					<div v-if="result.attachments.length" class="document-list"><div v-for="file in result.attachments" :key="file.name"><span>{{ __("Attachment") }}</span><a :href="file.file_url" target="_blank" rel="noopener">{{ file.file_name }}</a></div></div>
					<div v-else class="empty compact">{{ __("No attachments have been added.") }}</div>
				</section>
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Linked Documents") }}</h2></div>
					<div v-if="result.linked_documents.length" class="document-list"><div v-for="document in result.linked_documents" :key="`${document.doctype}-${document.name}`">
						<span>{{ __(document.doctype) }}</span><router-link v-if="documentRoute(document)" :to="documentRoute(document)"><bdi>{{ document.name }}</bdi></router-link><bdi v-else>{{ document.name }}</bdi><small>{{ documentStatus(document) }} · {{ date(document.date) }}</small>
					</div></div>
					<div v-else class="empty compact">{{ __("No linked documents.") }}</div>
				</section>
			</div>
			<p v-if="invoice.remarks" class="panel section-card detail-notes"><strong>{{ __("Notes") }}:</strong> {{ invoice.remarks }}</p>
			<SupplierPaymentDialog ref="paymentDialog" :purchase-invoice="invoice.name" @created="paymentCreated" />
		</template>
	</div>
</template>
