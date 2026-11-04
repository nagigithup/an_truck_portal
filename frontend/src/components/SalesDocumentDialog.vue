<script setup>
import { computed, inject, ref } from "vue";
import { call, uploadFile, __ } from "../api";
import FormField from "./FormField.vue";
import TemplateSpecifications from "./TemplateSpecifications.vue";

const props = defineProps({
	doctype: { type: String, required: true },
	sourceName: { type: String, default: "" },
});
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null);
const busy = ref("");
const error = ref("");
const source = ref(null);
const sources = ref([]);
const selectedSource = ref("");
const form = ref({});
const attachment = ref(null);
const creationResult = ref(null);
const attachmentUploaded = ref(false);
const operationKey = ref("");
const editName = ref("");
const pricingRequests = new WeakMap();
const rateEdits = new WeakMap();
function markRate(row) { rateEdits.set(row, (rateEdits.get(row) || 0) + 1); }
const title = computed(() => editName.value ? "Edit Quotation" : `Create ${props.doctype}`);

async function reprice() {
	const priceList = source.value?.price_lists?.find(entry => entry.name === form.value.selling_price_list);
	if (priceList) form.value.currency = priceList.currency;
	for (const row of form.value.items || []) if (row.item_code) await selectItem(row);
}

const sourceDoctype = computed(() =>
	props.doctype === "Sales Order" ? "Quotation" : props.doctype === "Sales Invoice" ? "Sales Order" : "",
);
const hasFixedSource = computed(() => !!props.sourceName);
const sourceOptions = computed(() =>
	sources.value.map((row) => ({
		value: row.name,
		label: `${row.name} · ${row.customer_name || row.party_name || row.customer || ""}`,
	})),
);

function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

function blankItem() {
	return {
		vehicle_master: "",
		vin: "",
		item_code: "",
		item_name: "",
		description: "",
		qty: 1,
		rate: 0,
		warehouse: "",
	};
}

async function selectItem(row) {
	const item = source.value?.item_options?.find((entry) => entry.name === row.item_code);
	if (item) Object.assign(row, { item_name: item.item_name, uom: item.stock_uom, rate: item.standard_rate || row.rate });
	if (props.doctype === "Quotation" && form.value.customer && row.item_code) {
		const request = (pricingRequests.get(row) || 0) + 1;
		pricingRequests.set(row, request);
		const requestedCode = row.item_code, initialRate = row.rate, editSequence = rateEdits.get(row) || 0;
		try {
			const result = await call("an_truck_portal.api.vehicle_quotation.item_details", {
				item_code: row.item_code, customer: form.value.customer, company: form.value.company,
				price_list: form.value.selling_price_list, transaction_date: form.value.transaction_date, qty: row.qty,
				currency: form.value.currency,
			});
			if (pricingRequests.get(row) !== request || row.item_code !== requestedCode) return;
			Object.assign(row, { item_name: result.item_name, uom: result.uom });
			// A delayed price lookup must not replace a rate entered meanwhile.
			if (row.rate === initialRate && (rateEdits.get(row) || 0) === editSequence) row.rate = result.rate ?? result.price_list_rate ?? 0;
		} catch (e) { if (pricingRequests.get(row) === request) error.value = e.message; }
	}
}

async function selectVehicle(row) {
	const vehicle = source.value?.vehicle_options?.find(
		(entry) => entry.name === row.vehicle_master,
	);
	if (!vehicle) return;
	const enteredRate = row.rate;
	if (props.doctype === "Quotation" && !row.custom_vehicle_specification_template) {
		row.custom_vehicle_specification_template = vehicle.specification_template || "";
	}
	Object.assign(row, {
		vehicle_master: vehicle.name,
		vin: vehicle.vin,
		vehicle_import_file: vehicle.vehicle_import_file,
		item_code: vehicle.item_code,
		item_name: vehicle.item_name,
		qty: 1,
		description: row.description || vehicle.description || vehicle.item_name || "",
		warehouse: row.warehouse || vehicle.warehouse || "",
		rate: row.rate || (props.doctype === "Quotation" ? 0 : vehicle.rate) || 0,
		vehicle_info: [vehicle.brand, vehicle.model, vehicle.color, __(vehicle.vehicle_status)]
			.filter(Boolean)
			.join(" · "),
	});
	if (props.doctype === "Quotation" && !enteredRate) await selectItem(row);
}

async function selectCustomer() {
	const customer = source.value?.customers?.find((entry) => entry.name === form.value.customer);
	form.value.currency = customer?.default_currency || source.value?.currency || "";
	if (props.doctype === "Quotation") await reprice();
}

async function loadSource() {
	source.value = null;
	const result = await call("an_truck_portal.api.sales.get_sales_form", {
		doctype: props.doctype,
		source: selectedSource.value,
		company: ctx.company,
		document: editName.value,
	});
	source.value = result;
	form.value = {
		modified: result.modified,
		customer: result.customer || "",
		company: result.company || ctx.company,
		currency: result.currency || "",
		transaction_date: result.transaction_date || "",
		valid_till: result.valid_till || "",
		delivery_date: result.delivery_date || "",
		posting_date: result.posting_date || "",
		due_date: result.due_date || "",
		remarks: result.remarks || "",
		selling_price_list: result.selling_price_list || "",
		taxes_and_charges: result.taxes_and_charges || "",
		custom_company_bank_account: result.custom_company_bank_account || "",
		items: result.items?.length ? result.items.map((row) => ({ ...row })) : [blankItem()],
	};
	form.value.items.forEach((row) => {
		if (row.vehicle_master && !editName.value) selectVehicle(row);
	});
}

async function open(documentName = "") {
	editName.value = typeof documentName === "string" ? documentName : "";
	error.value = "";
	busy.value = "";
	source.value = null;
	sources.value = [];
	attachment.value = null;
	creationResult.value = null;
	attachmentUploaded.value = false;
	operationKey.value = key();
	selectedSource.value = props.sourceName;
	form.value = {};
	dialog.value?.showModal();
	try {
		if (sourceDoctype.value && !hasFixedSource.value) {
			const filters =
				sourceDoctype.value === "Quotation"
					? { docstatus: 1, status: ["not in", ["Ordered", "Lost", "Cancelled"]] }
					: {
							docstatus: 1,
							per_billed: ["<", 100],
							status: ["not in", ["Closed", "On Hold", "Cancelled"]],
						};
			const result = await call("an_truck_portal.api.records.list_records", {
				doctype: sourceDoctype.value,
				company: ctx.company,
				page_length: 100,
				filters,
			});
			sources.value = result.rows || [];
		}
		await loadSource();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	}
}

function close() {
	if (!busy.value) dialog.value?.close();
}

async function changeSource() {
	error.value = "";
	try {
		await loadSource();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	}
}

function chooseAttachment(event) {
	const file = event.target.files?.[0] || null;
	const extension = file?.name.split(".").pop()?.toLowerCase();
	if (
		file &&
		!["application/pdf", "image/jpeg", "image/png", "image/webp"].includes(file.type) &&
		!["pdf", "jpg", "jpeg", "png", "webp"].includes(extension)
	) {
		error.value = __("Unsupported file type. Upload a PDF, JPG, PNG, or WebP file.");
		event.target.value = "";
		attachment.value = null;
		return;
	}
	error.value = "";
	attachment.value = file;
}

async function save(submitNow) {
	if (busy.value || !source.value) return;
	if (!form.value.customer) {
		error.value = __("Customer is required.");
		return;
	}
	const items = (form.value.items || []).filter((row) => Number(row.qty) > 0);
	const vehicles = items.map((row) => row.vehicle_master).filter(Boolean);
	if (new Set(vehicles).size !== vehicles.length) {
		error.value = __("A VIN cannot be selected more than once.");
		return;
	}
	if (!items.length || items.some((row) => !row.item_code || Number(row.rate) < 0 || (row.max_qty && Number(row.qty) > Number(row.max_qty)))) {
		error.value = __("Enter valid item quantities and rates.");
		return;
	}
	busy.value = submitNow ? "submit" : "draft";
	error.value = "";
	try {
		if (!creationResult.value) {
			creationResult.value = await call(
				"an_truck_portal.api.sales.create_sales_document",
				{
					doctype: props.doctype,
					document: editName.value,
					source: selectedSource.value,
					data: { ...form.value, items },
					submit_now: submitNow ? 1 : 0,
					idempotency_key: operationKey.value,
				},
				true,
			);
		}
		if (attachment.value && !attachmentUploaded.value) {
			await uploadFile(attachment.value, props.doctype, creationResult.value.name, {
				method: "an_truck_portal.api.sales.upload_sales_attachment",
				fields: { doctype: props.doctype, document: creationResult.value.name },
			});
			attachmentUploaded.value = true;
		}
		dialog.value?.close();
		notification.value = __("Operation completed successfully: {0}", [creationResult.value.name]);
		emit("created", creationResult.value);
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = "";
	}
}

defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog wide-dialog" :aria-label="__(title)" @cancel.prevent="close">
		<form @submit.prevent="save(true)">
			<div class="dialog-head">
				<div><p class="eyebrow">{{ __("Sales") }}</p><h2>{{ __(title) }}</h2></div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid">
					<label v-if="sourceDoctype && !hasFixedSource" class="wide"><span>{{ __(sourceDoctype) }} ({{ __("Optional") }})</span><select v-model="selectedSource" :disabled="!!creationResult" @change="changeSource"><option value="">{{ __("Create directly") }}</option><option v-for="option in sourceOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
					<label v-else-if="sourceDoctype" class="wide"><span>{{ __(sourceDoctype) }}</span><input :value="selectedSource" disabled /></label>
					<label><span>{{ __("Customer") }}</span><select v-if="!selectedSource" v-model="form.customer" required :disabled="!!creationResult" @change="selectCustomer"><option value="">{{ __("Select") }}</option><option v-for="customer in source?.customers || []" :key="customer.name" :value="customer.name">{{ customer.customer_name || customer.name }}</option></select><input v-else :value="source?.customer_name || source?.customer" disabled /></label>
					<label><span>{{ __("Company") }}</span><input :value="form.company" disabled /></label>
					<label><span>{{ __("Currency") }}</span><input :value="form.currency" disabled /></label>
					<label v-if="doctype !== 'Sales Invoice'"><span>{{ __("Transaction Date") }}</span><input v-model="form.transaction_date" type="date" required :disabled="!!creationResult" /></label>
					<label v-if="doctype === 'Quotation'"><span>{{ __("Valid Till") }}</span><input v-model="form.valid_till" type="date" :disabled="!!creationResult" /></label>
					<label v-if="doctype === 'Quotation'"><span>{{ __("Price List") }}</span><select v-model="form.selling_price_list" :disabled="!!creationResult" @change="reprice"><option value="">{{ __("Select") }}</option><option v-for="entry in source?.price_lists || []" :key="entry.name" :value="entry.name">{{ entry.name }}</option></select></label>
					<label v-if="doctype === 'Quotation'"><span>{{ __("Taxes and Charges") }}</span><select v-model="form.taxes_and_charges" :disabled="!!creationResult"><option value="">{{ __("Company Default") }}</option><option v-for="entry in source?.tax_templates || []" :key="entry" :value="entry">{{ entry }}</option></select></label>
					<label v-if="doctype === 'Quotation'"><span>{{ __("Company Bank Account") }}</span><select v-model="form.custom_company_bank_account" :disabled="!!creationResult"><option value="">{{ __("Select") }}</option><option v-for="entry in source?.bank_accounts || []" :key="entry" :value="entry">{{ entry }}</option></select></label>
					<label v-if="doctype === 'Sales Order'"><span>{{ __("Delivery Date") }}</span><input v-model="form.delivery_date" type="date" required :disabled="!!creationResult" /></label>
					<label v-if="doctype === 'Sales Invoice'"><span>{{ __("Posting Date") }}</span><input v-model="form.posting_date" type="date" required :disabled="!!creationResult" /></label>
					<label v-if="doctype === 'Sales Invoice'"><span>{{ __("Due Date") }}</span><input v-model="form.due_date" type="date" :disabled="!!creationResult" /></label>
					<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.remarks" :disabled="!!creationResult"></textarea></label>
					<label class="wide document-attachment"><span>{{ __("Document Attachment") }}</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" :disabled="attachmentUploaded" @change="chooseAttachment" /><small>{{ __("Supported files: PDF, JPG, PNG, WebP") }}</small></label>
				</div>
				<div class="dialog-section-head"><h3>{{ __("Items") }}</h3><button type="button" class="button secondary small" :disabled="!!creationResult" @click="form.items.push(blankItem())">{{ __("+ Add Item") }}</button></div>
				<div class="editable-grid purchase-items"><div v-for="(row, index) in form.items || []" :key="row.source_item || index" class="edit-row sales-item-row" :class="{ 'quotation-item-row': doctype === 'Quotation' }">
					<label class="sales-item-vin"><span>{{ __("VIN / Chassis Number") }}</span><input v-model="row.vehicle_master" list="sales-vehicle-options" :disabled="!!creationResult" @change="selectVehicle(row)" /><small v-if="row.vehicle_info || row.vin" class="table-subtitle">{{ row.vehicle_info || row.vin }}</small></label>
					<label class="sales-item-name"><span>{{ __("Item Name") }}</span><input v-model="row.item_name" disabled /></label>
					<label class="sales-item-quantity"><span>{{ __("Quantity") }}</span><input v-model.number="row.qty" type="number" min="0" :max="row.max_qty" step="any" required :disabled="!!creationResult" /></label>
					<label class="sales-item-description"><span>{{ __("Description") }}</span><input v-model="row.description" :disabled="!!creationResult" /></label>
					<label class="sales-item-rate"><span>{{ __("Rate") }}</span><input v-model.number="row.rate" type="number" min="0" step="any" required :disabled="!!creationResult" @input="markRate(row)" /></label>
					<label class="sales-item-warehouse"><span>{{ __("Warehouse") }}</span><input v-model="row.warehouse" :disabled="!!creationResult" /></label>
					<label class="sales-item-code"><span>{{ __("Item Code") }}</span><input v-model="row.item_code" list="sales-item-options" required :disabled="!!row.source_item || !!row.vehicle_master || !!creationResult" @change="selectItem(row)" /></label>
					<template v-if="doctype === 'Quotation'">
						<FormField v-model="row.custom_vehicle_specification_template" :label="__('Specification Template / Configuration')" :link="{ method: 'an_truck_portal.api.vehicle_quotation.template_options', item_code: row.item_code }" :disabled="!row.item_code || !!creationResult" />
						<label><span>{{ __('Vehicle Warranty Terms') }}</span><textarea v-model="row.custom_vehicle_warranty_terms" :placeholder="__('Template warranty terms apply when empty')" :disabled="!!creationResult"></textarea></label>
						<label><span>{{ __('Vehicle Delivery Conditions') }}</span><textarea v-model="row.custom_vehicle_delivery_terms" :disabled="!!creationResult"></textarea></label>
						<TemplateSpecifications :template="row.custom_vehicle_specification_template" />
					</template>
					<button type="button" class="remove-row" :disabled="!!creationResult" :aria-label="__('Delete')" @click="form.items.splice(index, 1)">×</button>
				</div></div>
				<datalist id="sales-vehicle-options"><option v-for="vehicle in source?.vehicle_options || []" :key="vehicle.name" :value="vehicle.name">{{ vehicle.vin || vehicle.chassis_number }} · {{ vehicle.item_name }} · {{ __(vehicle.vehicle_status) }}</option></datalist>
				<datalist id="sales-item-options"><option v-for="item in source?.item_options || []" :key="item.name" :value="item.name">{{ item.item_name }}</option></datalist>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" :disabled="!!busy" @click="close">{{ __("Cancel") }}</button><button type="button" class="button secondary" :disabled="!!busy" @click="save(false)">{{ busy === "draft" ? __("Saving…") : __("Save Draft") }}</button><button class="button" :disabled="!!busy">{{ busy === "submit" ? __("Processing...") : creationResult ? __("Retry Upload") : __("Create and Submit") }}</button></div>
		</form>
	</dialog>
</template>

<style scoped>
.quotation-item-row {grid-template-columns:repeat(2,minmax(0,1fr));grid-template-areas:none;}
.quotation-item-row > * {grid-area:auto;min-width:0;}
.quotation-item-row .sales-item-code {order:-2;}
.quotation-item-row .sales-item-name {order:-1;}
.quotation-item-row .vehicle-form-section {grid-column:1/-1;}
.quotation-item-row .remove-row {grid-area:auto;grid-column:1/-1;justify-self:end;width:42px;}
@media(max-width:700px) {.quotation-item-row {grid-template-columns:minmax(0,1fr);}}
</style>
