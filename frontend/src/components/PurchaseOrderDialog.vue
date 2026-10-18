<script setup>
import { computed, inject, ref } from "vue";
import { call, uploadFile, __ } from "../api";

const props = defineProps({
	vehicleImportFile: { type: String, default: "" },
	supplier: { type: String, default: "" },
	currency: { type: String, default: "" },
});
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null);
const busy = ref(false);
const error = ref("");
const options = ref(null);
const importFiles = ref([]);
const selectedImportFile = ref("");
const selectedSupplier = ref("");
const selectedCurrency = ref("");
const attachment = ref(null);
const creationResult = ref(null);
const attachmentUploaded = ref(false);
const operationKey = ref("");
const eligibleImportFile = ref(false);
const form = ref({ required_by_date: "", notes: "", items: [] });

const hasFixedImportFile = computed(() => !!props.vehicleImportFile);
const importFileOptions = computed(() =>
	importFiles.value.map((row) => ({
		value: row.name,
		label: row.import_title ? `${row.import_title} (${row.name})` : row.name,
	})),
);

function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

function blankItem() {
	return { item_code: "", item_name: "", qty: 1, rate: 0, uom: "", warehouse: "" };
}

async function loadContext() {
	if (!selectedImportFile.value) {
		options.value = null;
		eligibleImportFile.value = false;
		selectedSupplier.value = "";
		selectedCurrency.value = "";
		return;
	}
	const row = importFiles.value.find((entry) => entry.name === selectedImportFile.value);
	selectedSupplier.value = props.supplier || row?.supplier || "";
	selectedCurrency.value = props.currency || row?.supplier_currency || "";
	if (!hasFixedImportFile.value) {
		const workspace = await call("an_truck.transactions.get_import_workspace", {
			vehicle_import_file: selectedImportFile.value,
		});
		if (!workspace.next_actions?.includes("create_purchase_order")) {
			options.value = null;
			eligibleImportFile.value = false;
			throw Error(__("A Purchase Order cannot be created for this Vehicle Import File."));
		}
	}
	options.value = await call("an_truck.transactions.get_import_form_options", {
		vehicle_import_file: selectedImportFile.value,
	});
	eligibleImportFile.value = true;
	if (!form.value.required_by_date) form.value.required_by_date = options.value.today;
}

async function open() {
	error.value = "";
	busy.value = false;
	options.value = null;
	attachment.value = null;
	creationResult.value = null;
	attachmentUploaded.value = false;
	eligibleImportFile.value = false;
	operationKey.value = key();
	form.value = { required_by_date: "", notes: "", items: [blankItem()] };
	try {
		if (hasFixedImportFile.value) {
			selectedImportFile.value = props.vehicleImportFile;
			selectedSupplier.value = props.supplier;
			selectedCurrency.value = props.currency;
			eligibleImportFile.value = true;
		} else {
			const result = await call("an_truck_portal.api.records.list_records", {
				doctype: "Vehicle Import File",
				company: ctx.company,
				page_length: 100,
				filters: { status: ["not in", ["Completed", "Cancelled"]] },
			});
			importFiles.value = result.rows || [];
			selectedImportFile.value = importFiles.value.length === 1 ? importFiles.value[0].name : "";
		}
		if (selectedImportFile.value) await loadContext();
		dialog.value?.showModal();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
		dialog.value?.showModal();
	}
}

function close() {
	if (!busy.value) dialog.value?.close();
}

async function changeImportFile() {
	error.value = "";
	try {
		await loadContext();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	}
}

function selectItem(row) {
	const item = options.value?.items?.find((entry) => entry.name === row.item_code);
	if (item) Object.assign(row, { item_name: item.item_name, uom: item.stock_uom });
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

async function submit() {
	if (busy.value) return;
	if (!selectedImportFile.value) {
		error.value = __("Select a Vehicle Import File.");
		return;
	}
	if (!eligibleImportFile.value) {
		error.value = __("A Purchase Order cannot be created for this Vehicle Import File.");
		return;
	}
	if (
		!form.value.items.length ||
		form.value.items.some((row) => !row.item_code || Number(row.qty) <= 0)
	) {
		error.value = __("Enter an item and a positive quantity for every row.");
		return;
	}
	busy.value = true;
	error.value = "";
	try {
		if (!creationResult.value) {
			creationResult.value = await call(
				"an_truck_portal.api.import_file.create_purchase_order",
				{
					vehicle_import_file: selectedImportFile.value,
					data: form.value,
					submit_now: 1,
					idempotency_key: operationKey.value,
				},
				true,
			);
		}
		if (attachment.value && !attachmentUploaded.value) {
			await uploadFile(attachment.value, "Purchase Order", creationResult.value.name, {
				method: "an_truck_portal.api.import_file.upload_purchase_order_attachment",
				fields: { vehicle_import_file: selectedImportFile.value },
			});
			attachmentUploaded.value = true;
		}
		dialog.value?.close();
		notification.value = __("Operation completed successfully: {0}", [creationResult.value.name]);
		emit("created", creationResult.value);
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = false;
	}
}

defineExpose({ open });
</script>

<template>
	<dialog
		ref="dialog"
		class="operation-dialog"
		:aria-label="__('Create Purchase Order')"
		@cancel.prevent="close"
	>
		<form @submit.prevent="submit">
			<div class="dialog-head">
				<div>
					<p class="eyebrow">{{ __("Purchasing") }}</p>
					<h2>{{ __("Create Purchase Order") }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid">
					<label v-if="!hasFixedImportFile" class="wide">
						<span>{{ __("Vehicle Import File") }}</span>
						<select
							v-model="selectedImportFile"
							required
							:disabled="!!creationResult"
							@change="changeImportFile"
						>
							<option value="">{{ __("Select") }}</option>
							<option v-for="option in importFileOptions" :key="option.value" :value="option.value">
								{{ option.label }}
							</option>
						</select>
					</label>
					<label><span>{{ __("Supplier") }}</span><input :value="selectedSupplier" disabled /></label>
					<label><span>{{ __("Currency") }}</span><input :value="selectedCurrency" disabled /></label>
					<label>
						<span>{{ __("Required By Date") }}</span>
						<input v-model="form.required_by_date" type="date" required :disabled="!!creationResult" />
					</label>
					<label class="wide">
						<span>{{ __("Notes") }}</span>
						<textarea v-model="form.notes" :disabled="!!creationResult"></textarea>
					</label>
					<label class="wide document-attachment">
						<span>{{ __("Document Attachment") }}</span>
						<input
							type="file"
							accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
							:disabled="attachmentUploaded"
							@change="chooseAttachment"
						/>
						<small>{{ __("Supported files: PDF, JPG, PNG, WebP") }}</small>
					</label>
				</div>
				<div class="dialog-section-head">
					<h3>{{ __("Items") }}</h3>
					<button
						type="button"
						class="button secondary small"
						:disabled="!!creationResult"
						@click="form.items.push(blankItem())"
					>
						{{ __("+ Add Item") }}
					</button>
				</div>
				<div class="editable-grid purchase-items">
					<div v-for="(row, index) in form.items" :key="index" class="edit-row">
						<label>
							<span>{{ __("Item") }}</span>
							<input v-model="row.item_code" list="purchase-item-options" required :disabled="!!creationResult" @change="selectItem(row)" />
						</label>
						<label><span>{{ __("Quantity") }}</span><input v-model.number="row.qty" type="number" min="0.001" step="any" required :disabled="!!creationResult" /></label>
						<label><span>{{ __("Rate") }}</span><input v-model.number="row.rate" type="number" min="0" step="any" :disabled="!!creationResult" /></label>
						<label><span>{{ __("Warehouse") }}</span><input v-model="row.warehouse" list="purchase-warehouse-options" :disabled="!!creationResult" /></label>
						<button type="button" class="remove-row" :disabled="!!creationResult" :aria-label="__('Delete')" @click="form.items.splice(index, 1)">×</button>
					</div>
				</div>
				<datalist id="purchase-item-options">
					<option v-for="item in options?.items" :key="item.name" :value="item.name">{{ item.item_name }}</option>
				</datalist>
				<datalist id="purchase-warehouse-options">
					<option v-for="warehouse in options?.warehouses" :key="warehouse.name" :value="warehouse.name"></option>
				</datalist>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="busy" @click="close">{{ __("Cancel") }}</button>
				<button class="button" :disabled="busy">
					{{ busy ? __("Processing...") : creationResult ? __("Retry Upload") : __("Create and Submit") }}
				</button>
			</div>
		</form>
	</dialog>
</template>
