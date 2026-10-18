<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import PurchaseInvoiceDialog from "../components/PurchaseInvoiceDialog.vue";

const props = defineProps({ name: String });
const state = ref("loading");
const error = ref("");
const result = ref(null);
const purchaseInvoiceDialog = ref(null);
const order = computed(() => result.value?.purchase_order || {});

function amount(value) {
	if (value == null || value === "") return "—";
	try {
		return new Intl.NumberFormat(document.documentElement.lang, {
			style: "currency",
			currency: order.value.currency || "SAR",
			maximumFractionDigits: 2,
		}).format(Number(value));
	} catch {
		return `${Number(value).toLocaleString()} ${order.value.currency || ""}`;
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

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		result.value = await call("an_truck_portal.api.import_file.get_purchase_order", {
			purchase_order: props.name,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}

onMounted(load);
watch(() => props.name, load);
</script>

<template>
	<div class="page purchase-order-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __("Purchase Order Details") }}</p>
					<h1><bdi>{{ order.name }}</bdi></h1>
					<div class="page-actions detail-actions">
						<router-link
							v-if="order.vehicle_import_file"
							:to="{ name: 'import-workspace', params: { name: order.vehicle_import_file } }"
						>
							{{ __("Vehicle Import File") }}: <bdi>{{ order.vehicle_import_file }}</bdi>
						</router-link>
						<button v-if="result.can_create_purchase_invoice" type="button" class="button small" @click="purchaseInvoiceDialog.open()">
							{{ __("+ Create Purchase Invoice") }}
						</button>
					</div>
				</div>
				<div class="workspace-metrics">
					<div><small>{{ __("Status") }}</small><span class="badge neutral">{{ documentStatus(order) }}</span></div>
					<div><small>{{ __("Supplier") }}</small><b>{{ order.supplier_name || order.supplier }}</b></div>
					<div><small>{{ __("Company") }}</small><b>{{ order.company }}</b></div>
					<div><small>{{ __("Date") }}</small><b>{{ date(order.transaction_date) }}</b></div>
					<div><small>{{ __("Required By Date") }}</small><b>{{ date(order.schedule_date) }}</b></div>
					<div><small>{{ __("Total") }}</small><b>{{ amount(order.grand_total) }}</b></div>
				</div>
			</header>

			<section class="panel section-card">
				<div class="section-head">
					<h2>{{ __("Items") }}</h2>
					<span class="badge neutral">{{ result.items.length }}</span>
				</div>
				<div class="table-wrap">
					<table>
						<thead><tr>
							<th>{{ __("Item") }}</th><th>{{ __("Description") }}</th><th>{{ __("Quantity") }}</th>
							<th>{{ __("Received Qty") }}</th><th>{{ __("Rate") }}</th><th>{{ __("Amount") }}</th>
							<th>{{ __("Warehouse") }}</th><th>{{ __("Required By Date") }}</th>
						</tr></thead>
						<tbody>
							<tr v-for="item in result.items" :key="item.name">
								<td><bdi>{{ item.item_code }}</bdi><small class="table-subtitle">{{ item.item_name }}</small></td>
								<td>{{ item.description || "—" }}</td><td>{{ item.qty }} {{ item.uom }}</td>
								<td>{{ item.received_qty }}</td><td>{{ amount(item.rate) }}</td><td>{{ amount(item.amount) }}</td>
								<td>{{ item.warehouse || "—" }}</td><td>{{ date(item.schedule_date) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<div class="workspace-grid lower-grid">
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Totals") }}</h2></div>
					<div class="compact-details">
						<div><small>{{ __("Total Quantity") }}</small><b>{{ order.total_qty }}</b></div>
						<div><small>{{ __("Net Total") }}</small><b>{{ amount(order.net_total) }}</b></div>
						<div><small>{{ __("Taxes and Charges") }}</small><b>{{ amount(order.total_taxes_and_charges) }}</b></div>
						<div><small>{{ __("Grand Total") }}</small><b>{{ amount(order.grand_total) }}</b></div>
					</div>
					<p v-if="order.remarks" class="detail-notes"><strong>{{ __("Notes") }}:</strong> {{ order.remarks }}</p>
				</section>
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Attachments") }}</h2></div>
					<div v-if="result.attachments.length" class="document-list">
						<div v-for="file in result.attachments" :key="file.name">
							<span>{{ __("Attachment") }}</span>
							<a :href="file.file_url" target="_blank" rel="noopener">{{ file.file_name }}</a>
						</div>
					</div>
					<div v-else class="empty compact">{{ __("No attachments have been added.") }}</div>
				</section>
			</div>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Linked Documents") }}</h2></div>
				<div v-if="result.linked_documents.length" class="document-list">
					<div v-for="document in result.linked_documents" :key="`${document.doctype}-${document.name}`">
						<span>{{ __(document.doctype) }}</span>
						<router-link v-if="document.doctype === 'Purchase Invoice'" :to="{ name: 'purchase-invoice-detail', params: { name: document.name } }"><bdi>{{ document.name }}</bdi></router-link>
						<router-link v-else-if="document.doctype === 'Purchase Receipt'" :to="{ name: 'purchase-receipt-detail', params: { name: document.name } }"><bdi>{{ document.name }}</bdi></router-link>
						<bdi v-else>{{ document.name }}</bdi>
						<small>{{ documentStatus(document) }} · {{ date(document.date) }}</small>
					</div>
				</div>
				<div v-else class="empty compact">{{ __("No linked documents.") }}</div>
			</section>
			<PurchaseInvoiceDialog ref="purchaseInvoiceDialog" :purchase-order="order.name" @created="load" />
		</template>
	</div>
</template>
