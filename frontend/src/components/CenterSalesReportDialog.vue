<script setup>
import { inject, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ center: String });
const emit = defineEmits(["saved"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null), source = ref(null), form = ref({}), itemInfo = ref(null);
const report = ref(""), modified = ref(""), busy = ref(""), error = ref(""), operationKey = ref("");
let priceTimer;
function key() { return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`; }
function amount(value) { return `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${itemInfo.value?.currency || ""}`; }
async function open(name = "") {
	report.value = name; modified.value = ""; error.value = ""; itemInfo.value = null; busy.value = "load"; operationKey.value = key(); dialog.value?.showModal();
	try {
		source.value = await call("an_truck_portal.api.center_sales.get_report_form", { center: props.center, company: ctx.company, report: name || undefined });
		form.value = { ...source.value.record }; modified.value = source.value.modified || "";
		if (form.value.item_code) await loadItem();
	} catch (e) { error.value = e.message; }
	finally { busy.value = ""; }
}
function close() { if (!busy.value) dialog.value?.close(); }
async function loadItem() {
	itemInfo.value = null;
	if (!form.value.item_code || !form.value.sale_date) return;
	try { itemInfo.value = await call("an_truck_portal.api.center_sales.get_report_item", { center: props.center, company: ctx.company, item_code: form.value.item_code, sale_date: form.value.sale_date }); error.value = ""; }
	catch (e) { error.value = e.message; }
}
watch(() => [form.value.item_code, form.value.sale_date], () => { clearTimeout(priceTimer); priceTimer = setTimeout(loadItem, 250); });
async function save(finalizeNow) {
	if (busy.value || !form.value.sale_date || !form.value.item_code || !(Number(form.value.quantity) > 0)) { error.value = __("Enter a sale date, item, and quantity greater than zero."); return; }
	busy.value = finalizeNow ? "finalize" : "draft";
	try {
		const result = await call("an_truck_portal.api.center_sales.save_report", { center: props.center, company: ctx.company, data: form.value, report: report.value || undefined, modified: modified.value || undefined, finalize_now: finalizeNow ? 1 : 0, idempotency_key: operationKey.value }, true);
		dialog.value?.close(); notification.value = __(finalizeNow ? "Reported sale finalized and invoiced successfully." : "Reported sale saved as Draft."); emit("saved", result);
	} catch (e) { error.value = e.message; }
	finally { busy.value = ""; }
}
defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog" :aria-label="__('Report Sales')" @cancel.prevent="close">
		<form @submit.prevent="save(true)">
			<div class="dialog-head"><div><p class="eyebrow">{{ __("Center Stock") }}</p><h2>{{ __(report ? "Edit Reported Sale" : "Report Sales") }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div>
			<div class="dialog-body">
				<div class="form-grid">
					<label><span>{{ __("Sale Date") }}</span><input v-model="form.sale_date" type="date" required /></label>
					<label><span>{{ __("Item") }}</span><input v-model="form.item_code" list="center-report-items" required ltr /></label>
					<label><span>{{ __("Quantity") }}</span><input v-model.number="form.quantity" type="number" min="0" step="any" required /></label>
					<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.notes"></textarea></label>
				</div>
				<datalist id="center-report-items"><option v-for="item in source?.items || []" :key="item.name" :value="item.name">{{ item.item_name }} · {{ __("Available Quantity") }}: {{ item.available_qty }}</option></datalist>
				<div v-if="itemInfo" class="compact-details"><div><small>{{ __("Available Quantity") }}</small><b>{{ itemInfo.available_qty }} {{ itemInfo.stock_uom }}</b></div><div><small>{{ __("Supply Price") }}</small><b>{{ amount(itemInfo.supply_price) }}</b></div><div><small>{{ __("Reference Retail Price") }}</small><b>{{ amount(itemInfo.retail_price) }}</b></div><div><small>{{ __("Center Margin Per Unit") }}</small><b>{{ amount(itemInfo.center_margin) }}</b></div></div>
				<p class="notice compact">{{ __("Saving a Draft has no stock or accounting effect. Finalizing creates and submits one update-stock Sales Invoice.") }}</p>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" :disabled="!!busy" @click="close">{{ __("Cancel") }}</button><button type="button" class="button secondary" :disabled="!!busy || !source?.can_write" @click="save(false)">{{ __(busy === "draft" ? "Saving…" : "Save Draft") }}</button><button class="button" :disabled="!!busy || !source?.can_submit">{{ __(busy === "finalize" ? "Processing..." : "Finalize and Invoice") }}</button></div>
		</form>
	</dialog>
</template>
