<script setup>
import { computed, inject, ref } from "vue";
import { call, uploadFile, __ } from "../api";

const props = defineProps({ purchaseOrder: { type: String, default: "" } });
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null);
const busy = ref("");
const error = ref("");
const purchaseOrders = ref([]);
const selectedPurchaseOrder = ref("");
const source = ref(null);
const attachment = ref(null);
const creationResult = ref(null);
const attachmentUploaded = ref(false);
const operationKey = ref("");
const form = ref({});

const hasFixedPurchaseOrder = computed(() => !!props.purchaseOrder);
const purchaseOrderOptions = computed(() =>
	purchaseOrders.value.map((row) => ({
		value: row.name,
		label: `${row.name} · ${row.supplier}`,
	})),
);

function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

function amount(value) {
	try {
		return new Intl.NumberFormat(document.documentElement.lang, {
			style: "currency",
			currency: source.value?.currency || "SAR",
			maximumFractionDigits: 2,
		}).format(Number(value) || 0);
	} catch {
		return `${Number(value || 0).toLocaleString()} ${source.value?.currency || ""}`;
	}
}

async function loadSource() {
	source.value = null;
	if (!selectedPurchaseOrder.value) return;
	const result = await call("an_truck_portal.api.import_file.get_purchase_invoice_form", {
		purchase_order: selectedPurchaseOrder.value,
	});
	source.value = result;
	form.value = {
		posting_date: result.posting_date,
		due_date: result.due_date || result.posting_date,
		supplier_invoice_number: "",
		supplier_invoice_date: "",
		remarks: "",
		items: result.items.map((row) => ({ ...row })),
	};
}

async function open() {
	error.value = "";
	busy.value = "";
	source.value = null;
	attachment.value = null;
	creationResult.value = null;
	attachmentUploaded.value = false;
	operationKey.value = key();
	form.value = {};
	try {
		if (hasFixedPurchaseOrder.value) {
			selectedPurchaseOrder.value = props.purchaseOrder;
		} else {
			const result = await call("an_truck_portal.api.records.list_records", {
				doctype: "Purchase Order",
				company: ctx.company,
				page_length: 100,
				filters: {
					docstatus: 1,
					per_billed: ["<", 100],
					status: ["not in", ["Closed", "On Hold"]],
				},
			});
			purchaseOrders.value = result.rows || [];
			selectedPurchaseOrder.value = purchaseOrders.value.length === 1 ? purchaseOrders.value[0].name : "";
		}
		if (selectedPurchaseOrder.value) await loadSource();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	}
	dialog.value?.showModal();
}

function close() {
	if (!busy.value) dialog.value?.close();
}

async function changePurchaseOrder() {
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
	if (busy.value) return;
	if (!selectedPurchaseOrder.value || !source.value) {
		error.value = __("Select a Purchase Order.");
		return;
	}
	const selectedItems = (form.value.items || []).filter((row) => Number(row.qty) > 0);
	if (
		!selectedItems.length ||
		(form.value.items || []).some(
			(row) => Number(row.qty) < 0 || Number(row.qty) > Number(row.max_qty) || Number(row.rate) < 0,
		)
	) {
		error.value = __("Enter valid quantities within the remaining unbilled quantities.");
		return;
	}
	busy.value = submitNow ? "submit" : "draft";
	error.value = "";
	try {
		if (!creationResult.value) {
			creationResult.value = await call(
				"an_truck_portal.api.import_file.create_purchase_invoice",
				{
					vehicle_import_file: source.value.vehicle_import_file,
					data: {
						...form.value,
						items: selectedItems,
						source_type: "Purchase Order",
						source_name: selectedPurchaseOrder.value,
					},
					submit_now: submitNow ? 1 : 0,
					idempotency_key: operationKey.value,
				},
				true,
			);
		}
		if (attachment.value && !attachmentUploaded.value) {
			await uploadFile(attachment.value, "Purchase Invoice", creationResult.value.name, {
				method: "an_truck_portal.api.import_file.upload_purchase_invoice_attachment",
				fields: { vehicle_import_file: source.value.vehicle_import_file },
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
	<dialog ref="dialog" class="operation-dialog wide-dialog" :aria-label="__('Create Purchase Invoice')" @cancel.prevent="close">
		<form @submit.prevent="save(true)">
			<div class="dialog-head">
				<div><p class="eyebrow">{{ __("Purchasing") }}</p><h2>{{ __("Create Purchase Invoice") }}</h2></div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid">
					<label v-if="!hasFixedPurchaseOrder" class="wide">
						<span>{{ __("Purchase Order") }}</span>
						<select v-model="selectedPurchaseOrder" required :disabled="!!creationResult" @change="changePurchaseOrder">
							<option value="">{{ __("Select") }}</option>
							<option v-for="option in purchaseOrderOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
						</select>
					</label>
					<label v-else class="wide"><span>{{ __("Purchase Order") }}</span><input :value="selectedPurchaseOrder" disabled /></label>
					<label><span>{{ __("Supplier") }}</span><input :value="source?.supplier_name || source?.supplier" disabled /></label>
					<label><span>{{ __("Company") }}</span><input :value="source?.company" disabled /></label>
					<label><span>{{ __("Currency") }}</span><input :value="source?.currency" disabled /></label>
					<label><span>{{ __("Posting Date") }}</span><input v-model="form.posting_date" type="date" required :disabled="!!creationResult" /></label>
					<label><span>{{ __("Due Date") }}</span><input v-model="form.due_date" type="date" :disabled="!!creationResult" /></label>
					<label><span>{{ __("Supplier Invoice Number") }}</span><input v-model="form.supplier_invoice_number" :disabled="!!creationResult" /></label>
					<label><span>{{ __("Supplier Invoice Date") }}</span><input v-model="form.supplier_invoice_date" type="date" :disabled="!!creationResult" /></label>
					<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.remarks" :disabled="!!creationResult"></textarea></label>
					<label class="wide document-attachment">
						<span>{{ __("Supplier Invoice Attachment") }}</span>
						<input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" :disabled="attachmentUploaded" @change="chooseAttachment" />
						<small>{{ __("Supported files: PDF, JPG, PNG, WebP") }}</small>
					</label>
				</div>

				<div class="dialog-section-head"><h3>{{ __("Items") }}</h3><p>{{ __("Remaining unbilled quantities") }}</p></div>
				<div class="table-wrap input-table">
					<table>
						<thead><tr><th>{{ __("Item") }}</th><th>{{ __("Description") }}</th><th>{{ __("Remaining Qty") }}</th><th>{{ __("Invoice Quantity") }}</th><th>{{ __("Rate") }}</th><th>{{ __("Amount") }}</th></tr></thead>
						<tbody>
							<tr v-for="row in form.items || []" :key="row.source_item">
								<td><bdi>{{ row.item_code }}</bdi><small>{{ row.item_name }}</small></td><td>{{ row.description || "—" }}</td><td>{{ row.max_qty }} {{ row.uom }}</td>
								<td><input v-model.number="row.qty" type="number" min="0" :max="row.max_qty" step="any" required :disabled="!!creationResult" /></td>
								<td><input v-model.number="row.rate" type="number" min="0" step="any" required :disabled="!!creationResult" /></td>
								<td>{{ amount(Number(row.qty || 0) * Number(row.rate || 0)) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="!!busy" @click="close">{{ __("Cancel") }}</button>
				<button type="button" class="button secondary" :disabled="!!busy" @click="save(false)">{{ busy === "draft" ? __("Saving…") : __("Save Draft") }}</button>
				<button class="button" :disabled="!!busy">{{ busy === "submit" ? __("Processing...") : creationResult ? __("Retry Upload") : __("Create and Submit") }}</button>
			</div>
		</form>
	</dialog>
</template>
