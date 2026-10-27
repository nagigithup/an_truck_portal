<script setup>
import { computed, inject, ref, watch } from "vue";
import { call, __ } from "../api";

const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null);
const source = ref(null);
const form = ref({});
const busy = ref("");
const error = ref("");
const totals = ref(null);
const operationKey = ref("");
let previewTimer;

const currency = computed(() => source.value?.currency || "");
const selectedPriceList = computed(() => form.value.sale_type === "retail" ? source.value?.retail_price_list : source.value?.supply_price_list);
function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}
function blankItem() {
	return { item_code: "", item_name: "", qty: 1, rate: null, stock_uom: "", available_qty: 0 };
}
function amount(value) {
	return `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${currency.value}`;
}
async function open(options = {}) {
	error.value = "";
	totals.value = null;
	busy.value = "load";
	operationKey.value = key();
	dialog.value?.showModal();
	try {
		source.value = await call("an_truck_portal.api.spare_parts_sales.get_form", { company: ctx.company });
		const defaultTax = source.value.tax_templates.find((row) => row.is_default)?.name || "";
		const centerRow = options.center ? source.value.centers.find((row) => `${row.center_type}::${row.name}` === options.center) : null;
		form.value = { sale_type: options.sale_type || "retail", customer: "", center: centerRow?.name || "", center_type: centerRow?.center_type || "", supplier: "", company: source.value.company, posting_date: source.value.posting_date, source_warehouse: options.source_warehouse || (source.value.warehouses.length === 1 ? source.value.warehouses[0].value : ""), taxes_and_charges: defaultTax, notes: "", items: [blankItem()] };
		if (form.value.source_warehouse) await loadAvailability();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = "";
	}
}
function close() {
	if (!busy.value) dialog.value?.close();
}
async function loadAvailability() {
	if (!form.value.source_warehouse) return;
	try {
		const items = await call("an_truck_portal.api.spare_parts_sales.get_item_availability", { company: form.value.company, warehouse: form.value.source_warehouse, price_list: selectedPriceList.value });
		source.value.items = items;
		form.value.items.forEach(selectItem);
	} catch (e) {
		error.value = e.message;
	}
}
function selectItem(row) {
	const item = source.value?.items.find((value) => value.name === row.item_code);
	if (item) Object.assign(row, { item_name: item.item_name, stock_uom: item.stock_uom, available_qty: item.available_qty, rate: item.price_list_rate });
}
async function saleTypeChanged() {
	form.value.customer = ""; form.value.center = ""; form.value.center_type = ""; form.value.supplier = "";
	if (form.value.source_warehouse) await loadAvailability();
}
function centerChanged(event) {
	const [centerType, ...name] = event.target.value.split("::");
	form.value.center_type = centerType; form.value.center = name.join("::");
}
async function preview() {
	const buyerSelected = form.value.sale_type === "retail" ? form.value.customer : form.value.sale_type === "center" ? form.value.center : form.value.supplier;
	if (!buyerSelected || !form.value.source_warehouse || form.value.items.some((row) => !row.item_code || !(Number(row.qty) > 0))) {
		totals.value = null;
		return;
	}
	try {
		totals.value = await call("an_truck_portal.api.spare_parts_sales.preview", { data: form.value }, true);
		error.value = "";
	} catch (e) {
		error.value = e.message;
	}
}
watch(form, () => {
	clearTimeout(previewTimer);
	previewTimer = setTimeout(preview, 350);
}, { deep: true });
async function save(submitNow) {
	if (busy.value) return;
	const buyerSelected = form.value.sale_type === "retail" ? form.value.customer : form.value.sale_type === "center" ? form.value.center : form.value.supplier;
	if (!buyerSelected || !form.value.source_warehouse || form.value.items.some((row) => !row.item_code || !(Number(row.qty) > 0) || !(Number(row.rate) >= 0))) {
		error.value = __("Enter valid customer, warehouse, item quantities and rates.");
		return;
	}
	busy.value = submitNow ? "submit" : "draft";
	try {
		const result = await call("an_truck_portal.api.spare_parts_sales.create", { data: form.value, submit_now: submitNow ? 1 : 0, idempotency_key: operationKey.value }, true);
		dialog.value?.close();
		notification.value = __("Operation completed successfully: {0}", [result.name]);
		emit("created", result);
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = "";
	}
}
defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog wide-dialog" :aria-label="__('New Spare Parts Sale')" @cancel.prevent="close">
		<form @submit.prevent="save(true)">
			<div class="dialog-head"><div><p class="eyebrow">{{ __("Spare Parts Sales") }}</p><h2>{{ __("New Spare Parts Sale") }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div>
			<div class="dialog-body">
				<div class="form-grid">
					<label><span>{{ __("Sale Type") }}</span><select v-model="form.sale_type" required @change="saleTypeChanged"><option value="retail">{{ __("Direct Retail Sale") }}</option><option value="center" :disabled="!source?.supply_price_list">{{ __("Sell to Center") }}</option><option value="supplier" :disabled="!source?.supply_price_list">{{ __("Sell to Supplier Buyer") }}</option></select></label>
					<label v-if="form.sale_type === 'retail'"><span>{{ __("Customer") }}</span><select v-model="form.customer" required><option value="">{{ __("Select") }}</option><option v-for="row in source?.customers || []" :key="row.name" :value="row.name">{{ row.customer_name || row.name }}</option></select></label>
					<label v-else-if="form.sale_type === 'center'"><span>{{ __("Authorized Center") }}</span><select :value="form.center_type && form.center ? `${form.center_type}::${form.center}` : ''" required @change="centerChanged"><option value="">{{ __("Select") }}</option><option v-for="row in source?.centers || []" :key="`${row.center_type}::${row.name}`" :value="`${row.center_type}::${row.name}`">{{ row.label }}</option></select></label>
					<label v-else><span>{{ __("Supplier Buyer") }}</span><select v-model="form.supplier" required><option value="">{{ __("Select") }}</option><option v-for="row in source?.supplier_buyers || []" :key="row.name" :value="row.name">{{ row.supplier_name || row.name }}</option></select></label>
					<label><span>{{ __("Posting Date") }}</span><input v-model="form.posting_date" type="date" required /></label>
					<label><span>{{ __("Company") }}</span><input :value="form.company" disabled /></label>
					<label><span>{{ __("Price List") }}</span><input :value="selectedPriceList || __('Not configured')" disabled /></label>
					<label><span>{{ __("Source Warehouse") }}</span><select v-model="form.source_warehouse" required @change="loadAvailability"><option value="">{{ __("Select") }}</option><option v-for="row in source?.warehouses || []" :key="row.value" :value="row.value">{{ row.label }}</option></select></label>
					<label class="wide"><span>{{ __("Taxes") }}</span><select v-model="form.taxes_and_charges"><option value="">{{ __("No tax template") }}</option><option v-for="row in source?.tax_templates || []" :key="row.name" :value="row.name">{{ row.title || row.name }}</option></select></label>
					<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.notes"></textarea></label>
				</div>
				<div class="dialog-section-head"><h3>{{ __("Items") }}</h3><button type="button" class="button secondary small" @click="form.items.push(blankItem())">{{ __("+ Add Item") }}</button></div>
				<div class="editable-grid purchase-items"><div v-for="(row, index) in form.items || []" :key="index" class="edit-row spare-sale-row">
					<label><span>{{ __("Part Number") }}</span><input v-model="row.item_code" list="spare-sale-items" required ltr @change="selectItem(row)" /></label>
					<label><span>{{ __("Item Name") }}</span><input :value="row.item_name" disabled /></label>
					<label><span>{{ __("Available Quantity") }}</span><input :value="`${row.available_qty || 0} ${row.stock_uom || ''}`" disabled /></label>
					<label><span>{{ __("Quantity") }}</span><input v-model.number="row.qty" type="number" min="0" step="any" required /></label>
					<label><span>{{ __("Rate") }}</span><input v-model.number="row.rate" type="number" min="0" step="any" required :disabled="!source?.can_override_rate" /><small v-if="!source?.can_override_rate">{{ __("Loaded from the selected Price List") }}</small></label>
					<label><span>{{ __("Amount") }}</span><input :value="amount(Number(row.qty) * Number(row.rate))" disabled /></label>
					<button type="button" class="remove-row" :aria-label="__('Delete')" @click="form.items.splice(index, 1)">×</button>
				</div></div>
				<datalist id="spare-sale-items"><option v-for="item in source?.items || []" :key="item.name" :value="item.name">{{ item.item_name }} · {{ __("Available Quantity") }}: {{ item.available_qty }}</option></datalist>
				<div v-if="totals" class="compact-details spare-sale-totals"><div><small>{{ __("Net Total") }}</small><b>{{ amount(totals.net_total) }}</b></div><div><small>{{ __("Taxes and Charges") }}</small><b>{{ amount(totals.total_taxes_and_charges) }}</b><small v-for="tax in totals.taxes" :key="tax.description">{{ tax.description }}: {{ amount(tax.tax_amount) }}</small></div><div><small>{{ __("Grand Total") }}</small><b>{{ amount(totals.grand_total) }}</b></div></div>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" :disabled="!!busy" @click="close">{{ __("Cancel") }}</button><button type="button" class="button secondary" :disabled="!!busy" @click="save(false)">{{ busy === "draft" ? __("Saving…") : __("Save Draft") }}</button><button class="button" :disabled="!!busy">{{ busy === "submit" ? __("Processing...") : __("Create and Submit") }}</button></div>
		</form>
	</dialog>
</template>
