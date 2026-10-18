<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ name: String });
const state = ref("loading");
const error = ref("");
const result = ref(null);
const receipt = computed(() => result.value?.purchase_receipt || {});
const deskUrl = computed(
	() => `/app/purchase-receipt/${encodeURIComponent(receipt.value.name || props.name)}`,
);

function amount(value) {
	if (value == null || value === "") return "—";
	try {
		return new Intl.NumberFormat(document.documentElement.lang, {
			style: "currency",
			currency: receipt.value.currency || "SAR",
			maximumFractionDigits: 2,
		}).format(Number(value));
	} catch {
		return `${Number(value).toLocaleString()} ${receipt.value.currency || ""}`;
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
	if (document.doctype === "Purchase Invoice") {
		return { name: "purchase-invoice-detail", params: { name: document.name } };
	}
	if (document.doctype === "Landed Cost Voucher") {
		return { name: "landed-cost-detail", params: { name: document.name } };
	}
	return null;
}

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		result.value = await call("an_truck_portal.api.import_file.get_purchase_receipt", {
			purchase_receipt: props.name,
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
	<div class="page purchase-receipt-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __("Purchase Receipt Details") }}</p>
					<h1><bdi>{{ receipt.name }}</bdi></h1>
					<div class="page-actions detail-actions">
						<router-link
							v-if="receipt.vehicle_import_file"
							:to="{ name: 'import-workspace', params: { name: receipt.vehicle_import_file } }"
						>
							{{ __("Vehicle Import File") }}: <bdi>{{ receipt.vehicle_import_file }}</bdi>
						</router-link>
						<a class="button secondary small" :href="deskUrl" target="_blank" rel="noopener">
							{{ __("Open in Desk") }}
						</a>
					</div>
				</div>
				<div class="workspace-metrics">
					<div><small>{{ __("Status") }}</small><span class="badge neutral">{{ documentStatus(receipt) }}</span></div>
					<div><small>{{ __("Supplier") }}</small><b>{{ receipt.supplier_name || receipt.supplier }}</b></div>
					<div><small>{{ __("Company") }}</small><b>{{ receipt.company }}</b></div>
					<div><small>{{ __("Posting Date") }}</small><b>{{ date(receipt.posting_date) }}</b></div>
					<div><small>{{ __("Total Quantity") }}</small><b>{{ receipt.total_qty }}</b></div>
					<div><small>{{ __("Grand Total") }}</small><b>{{ amount(receipt.grand_total) }}</b></div>
				</div>
			</header>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Received Items") }}</h2><span class="badge neutral">{{ result.items.length }}</span></div>
				<div class="table-wrap"><table>
					<thead><tr>
						<th>{{ __("Item") }}</th><th>{{ __("Description") }}</th><th>{{ __("Received Qty") }}</th><th>{{ __("Accepted Qty") }}</th><th>{{ __("Rejected Qty") }}</th><th>{{ __("Warehouse") }}</th><th>{{ __("Rate") }}</th><th>{{ __("Amount") }}</th><th>{{ __("Purchase Order") }}</th>
					</tr></thead>
					<tbody><tr v-for="item in result.items" :key="item.name">
						<td><bdi>{{ item.item_code }}</bdi><small class="table-subtitle">{{ item.item_name }}</small></td><td>{{ item.description || "—" }}</td><td>{{ item.received_qty }} {{ item.uom }}</td><td>{{ item.qty }} {{ item.uom }}</td><td>{{ item.rejected_qty }} {{ item.uom }}</td><td>{{ item.warehouse || "—" }}</td><td>{{ amount(item.rate) }}</td><td>{{ amount(item.amount) }}</td>
						<td><router-link v-if="item.purchase_order" :to="{ name: 'purchase-order-detail', params: { name: item.purchase_order } }"><bdi>{{ item.purchase_order }}</bdi></router-link><span v-else>—</span></td>
					</tr></tbody>
				</table></div>
			</section>

			<div class="workspace-grid lower-grid">
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Totals") }}</h2></div>
					<div class="compact-details">
						<div><small>{{ __("Total Quantity") }}</small><b>{{ receipt.total_qty }}</b></div><div><small>{{ __("Net Total") }}</small><b>{{ amount(receipt.net_total) }}</b></div><div><small>{{ __("Taxes and Charges") }}</small><b>{{ amount(receipt.total_taxes_and_charges) }}</b></div><div><small>{{ __("Grand Total") }}</small><b>{{ amount(receipt.grand_total) }}</b></div>
					</div>
				</section>
				<section class="panel section-card">
					<div class="section-head"><h2>{{ __("Attachments") }}</h2></div>
					<div v-if="result.attachments.length" class="document-list"><div v-for="file in result.attachments" :key="file.name"><span>{{ __("Attachment") }}</span><a :href="file.file_url" target="_blank" rel="noopener">{{ file.file_name }}</a></div></div>
					<div v-else class="empty compact">{{ __("No attachments have been added.") }}</div>
				</section>
			</div>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Linked Documents") }}</h2></div>
				<div v-if="result.linked_documents.length" class="document-list"><div v-for="document in result.linked_documents" :key="`${document.doctype}-${document.name}`">
					<span>{{ __(document.doctype) }}</span><router-link v-if="documentRoute(document)" :to="documentRoute(document)"><bdi>{{ document.name }}</bdi></router-link><bdi v-else>{{ document.name }}</bdi><small>{{ documentStatus(document) }} · {{ date(document.date) }}</small>
				</div></div>
				<div v-else class="empty compact">{{ __("No linked documents.") }}</div>
			</section>
			<p v-if="receipt.remarks" class="panel section-card detail-notes"><strong>{{ __("Notes") }}:</strong> {{ receipt.remarks }}</p>
		</template>
	</div>
</template>
