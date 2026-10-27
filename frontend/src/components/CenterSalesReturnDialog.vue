<script setup>
import { inject, ref } from "vue";
import { call, __ } from "../api";

const props = defineProps({ center: { type: String, required: true } });
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null), source = ref(null), form = ref({}), busy = ref(false), error = ref("");
let operationKey = "";

function key() { return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`; }
async function open(invoice = "") {
	error.value = ""; busy.value = true; operationKey = key();
	form.value = { invoice, posting_date: "", notes: "", items: [] };
	dialog.value?.showModal();
	try {
		source.value = await call("an_truck_portal.api.maintenance_centers.get_sales_return_form", { center: props.center, company: ctx.company, invoice });
		form.value.posting_date = source.value.posting_date;
		if (invoice) form.value.items = source.value.items.map((row) => ({ ...row, qty: 0 }));
	} catch (e) { error.value = e.message; }
	finally { busy.value = false; }
}
async function invoiceChanged() {
	error.value = ""; busy.value = true;
	try {
		const result = await call("an_truck_portal.api.maintenance_centers.get_sales_return_form", { center: props.center, company: ctx.company, invoice: form.value.invoice });
		form.value.items = result.items.map((row) => ({ ...row, qty: 0 }));
	} catch (e) { error.value = e.message; }
	finally { busy.value = false; }
}
function close() { if (!busy.value) dialog.value?.close(); }
async function save() {
	if (busy.value || !form.value.invoice || !form.value.items.some((row) => Number(row.qty) > 0)) {
		error.value = __("Enter at least one return quantity."); return;
	}
	busy.value = true; error.value = "";
	try {
		const result = await call("an_truck_portal.api.maintenance_centers.create_sales_return", { center: props.center, company: ctx.company, invoice: form.value.invoice, data: form.value, idempotency_key: operationKey }, true);
		dialog.value?.close(); notification.value = __("Sales Return submitted successfully: {0}", [result.name]); emit("created", result);
	} catch (e) { error.value = e.message; }
	finally { busy.value = false; }
}
defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog wide-dialog" :aria-label="__('Sales Return')" @cancel.prevent="close">
		<form @submit.prevent="save">
			<div class="dialog-head"><div><p class="eyebrow">{{ __("Maintenance Center") }}</p><h2>{{ __("Sales Return") }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div>
			<div class="dialog-body">
				<p class="notice compact">{{ __("A submitted credit note returns stock against the original center invoice and reduces the receivable using standard ERPNext accounting.") }}</p>
				<div class="form-grid">
					<label class="wide"><span>{{ __("Sales Invoice") }}</span><select v-model="form.invoice" required :disabled="busy" @change="invoiceChanged"><option value="">{{ __("Select") }}</option><option v-for="row in source?.invoices || []" :key="row.name" :value="row.name">{{ row.name }} · {{ row.posting_date }}</option></select></label>
					<label><span>{{ __("Posting Date") }}</span><input v-model="form.posting_date" type="date" required /></label>
					<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.notes"></textarea></label>
				</div>
				<div v-if="form.items?.length" class="table-wrap"><table><thead><tr><th>{{ __("Item Code") }}</th><th>{{ __("Item Name") }}</th><th>{{ __("Warehouse") }}</th><th>{{ __("Returnable Quantity") }}</th><th>{{ __("Return Quantity") }}</th></tr></thead><tbody><tr v-for="row in form.items" :key="row.source_row"><td><bdi>{{ row.item_code }}</bdi></td><td>{{ row.item_name }}</td><td>{{ row.warehouse }}</td><td>{{ row.returnable_qty }} {{ row.stock_uom }}</td><td><input v-model.number="row.qty" type="number" min="0" :max="row.returnable_qty" step="any" /></td></tr></tbody></table></div>
				<p v-else-if="form.invoice && !busy" class="empty">{{ __("No quantities remain available to return.") }}</p>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" :disabled="busy" @click="close">{{ __("Cancel") }}</button><button class="button" :disabled="busy || !form.items?.length">{{ busy ? __("Processing...") : __("Create and Submit") }}</button></div>
		</form>
	</dialog>
</template>
