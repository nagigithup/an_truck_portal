<script setup>
import { computed, inject, ref } from "vue";
import { call, __ } from "../api";

const emit = defineEmits(["saved"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null), data = ref(null), busy = ref(false), error = ref("");
const margin = computed(() => data.value?.retail_price != null && data.value?.supply_price != null
	? Number(data.value.retail_price) - Number(data.value.supply_price) : null);
function amount(value) { return value == null ? "—" : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${data.value?.currency || ""}`; }
async function open(itemCode) {
	error.value = ""; data.value = null; busy.value = true; dialog.value?.showModal();
	try { data.value = await call("an_truck_portal.api.spare_parts_pricing.get_pricing", { item_code: itemCode, company: ctx.company }); }
	catch (e) { error.value = e.message; }
	finally { busy.value = false; }
}
function close() { if (!busy.value) dialog.value?.close(); }
async function save() {
	if (!data.value?.can_write || busy.value) return;
	busy.value = true;
	try {
		data.value = await call("an_truck_portal.api.spare_parts_pricing.save_pricing", { item_code: data.value.item_code, company: ctx.company, retail_price: data.value.retail_price, supply_price: data.value.supply_price }, true);
		notification.value = __("Prices saved successfully."); emit("saved", data.value); dialog.value?.close();
	} catch (e) { error.value = e.message; }
	finally { busy.value = false; }
}
defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog" :aria-label="__('Spare Parts Pricing')" @cancel.prevent="close">
		<form @submit.prevent="save">
			<div class="dialog-head"><div><p class="eyebrow">{{ __("Standard ERPNext Price Lists") }}</p><h2>{{ __("Spare Parts Pricing") }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div>
			<div class="dialog-body">
				<div v-if="data" class="form-grid">
					<label><span>{{ __("Item Code") }}</span><input :value="data.item_code" disabled /></label>
					<label><span>{{ __("Item Name") }}</span><input :value="data.item_name" disabled /></label>
					<label><span>{{ __("Valuation Cost (reference only)") }}</span><input :value="amount(data.valuation_cost)" disabled /><small>{{ __("This is ERPNext valuation cost, not an editable purchase price.") }}</small></label>
					<label><span>{{ __("Center Margin") }}</span><input :value="amount(margin)" disabled /></label>
					<label><span>{{ __("Retail Price") }} · {{ data.retail_price_list }}</span><input v-model.number="data.retail_price" type="number" min="0" step="any" required :disabled="!data.can_write" /></label>
					<label><span>{{ __("Supply Price") }} · {{ data.supply_price_list }}</span><input v-model.number="data.supply_price" type="number" min="0" step="any" required :disabled="!data.can_write" /></label>
				</div>
				<p v-if="data?.cost_missing" class="notice compact">{{ __("Valuation cost is missing for this item and company; prices cannot be saved.") }}</p>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" :disabled="busy" @click="close">{{ __(data?.can_write ? "Cancel" : "Close") }}</button><button v-if="data?.can_write" class="button" :disabled="busy || data.cost_missing">{{ __(busy ? "Saving…" : "Save") }}</button></div>
		</form>
	</dialog>
</template>
