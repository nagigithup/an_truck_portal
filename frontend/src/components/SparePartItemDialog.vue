<script setup>
import { computed, inject, nextTick, reactive, ref } from "vue";
import { call } from "../api";
import { __ } from "../i18n";
import FormField from "./FormField.vue";

const props = defineProps({ catalog: { type: String, default: "spare_parts" } });
const isTruck = computed(() => props.catalog === "trucks");
const emit = defineEmits(["saved"]);
const { notification } = inject("portal");
const dialog = ref(null);
const form = ref(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const itemGroups = ref([]);
const uoms = ref([]);
const itemName = ref("");
const modified = ref("");
const canWrite = ref(false);
const data = reactive({});
const editing = computed(() => Boolean(itemName.value));
const title = computed(() => __(isTruck.value ? (editing.value ? "Edit Truck Item" : "New Truck Item") : (editing.value ? "Edit Item" : "New Item")));

function reset() {
	Object.assign(data, {
		item_code: "",
		item_name: "",
		item_group: "",
		stock_uom: "",
		disabled: 0,
		is_stock_item: 1,
	});
	itemGroups.value = [];
	uoms.value = [];
	itemName.value = "";
	modified.value = "";
	canWrite.value = false;
	error.value = "";
}

async function open(name = "") {
	reset();
	itemName.value = name;
	dialog.value?.showModal();
	loading.value = true;
	try {
		const result = await call("an_truck_portal.api.spare_parts.get_item_form", {
			name: name || undefined,
			catalog: props.catalog,
		});
		Object.assign(data, result.record);
		itemGroups.value = result.item_groups;
		uoms.value = result.uoms;
		modified.value = result.modified || "";
		canWrite.value = result.can_write;
		if (!canWrite.value) error.value = __("You do not have permission to save items.");
		await nextTick();
		form.value?.querySelector("input:not(:disabled)")?.focus();
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
}

function close() {
	if (!saving.value) dialog.value?.close();
}

function validate() {
	if (!String(data.item_code || "").trim()) return __("Please enter an Item Code.");
	if (!String(data.item_name || "").trim()) return __("Please enter an Item Name.");
	if (!data.item_group) return __("Please select an Item Group.");
	if (!data.stock_uom) return __("Please select a Stock UOM.");
	if (isTruck.value && !editing.value && !data.is_stock_item) return __("Truck items must maintain stock and use serial numbers for VIN tracking.");
	return "";
}

async function save() {
	if (saving.value || loading.value || !canWrite.value) return;
	error.value = validate();
	if (error.value || !form.value.reportValidity()) return;
	saving.value = true;
	try {
		const result = await call(
			"an_truck_portal.api.spare_parts.save_item",
			{
				catalog: props.catalog,
				name: itemName.value || undefined,
				modified: modified.value || undefined,
				data: {
					item_code: String(data.item_code).trim(),
					item_name: String(data.item_name).trim(),
					item_group: data.item_group,
					stock_uom: data.stock_uom,
					disabled: data.disabled ? 1 : 0,
					is_stock_item: data.is_stock_item ? 1 : 0,
				},
			},
			true,
		);
		dialog.value?.close();
		notification.value = __(editing.value ? "Item updated successfully." : "Item created successfully.");
		emit("saved", result);
	} catch (e) {
		error.value = e.message;
	} finally {
		saving.value = false;
	}
}

defineExpose({ open });
</script>

<template>
	<dialog
		ref="dialog"
		class="operation-dialog"
		:aria-label="title"
		@cancel.prevent="close"
	>
		<form ref="form" @submit.prevent="save">
			<div class="dialog-head">
				<div>
					<p class="eyebrow">{{ __(isTruck ? "Truck Items" : "Spare Parts") }}</p>
					<h2>{{ title }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid create-import-grid">
					<FormField
						v-model="data.item_code"
						:label="__('Item Code')"
						:disabled="loading || editing || !canWrite"
						required
						ltr
					/>
					<FormField
						v-model="data.item_name"
						:label="__('Item Name')"
						:disabled="loading || !canWrite"
						required
					/>
					<FormField
						v-model="data.item_group"
						:label="__('Item Group')"
						type="select"
						:options="itemGroups"
						:loading="loading"
						:disabled="!canWrite"
						required
					/>
					<FormField
						v-model="data.stock_uom"
						:label="__('Stock UOM')"
						type="select"
						:options="uoms"
						:loading="loading"
						:disabled="!canWrite"
						required
					/>
					<div class="checkbox-field">
						<label>
							<input v-model="data.is_stock_item" type="checkbox" :true-value="1" :false-value="0" :disabled="loading || !canWrite" />
							<span>{{ __("Maintain Stock") }}</span>
						</label>
					</div>
					<div class="checkbox-field">
						<label>
							<input
								v-model="data.disabled"
								type="checkbox"
								:true-value="1"
								:false-value="0"
								:disabled="loading || !canWrite"
							/>
							<span>{{ __("Disabled") }}</span>
						</label>
					</div>
				</div>
				<p v-if="isTruck && !editing" class="notice compact">{{ __("Truck items use serial numbers for VIN tracking.") }}</p>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="saving" @click="close">
					{{ __(canWrite ? "Cancel" : "Close") }}
				</button>
				<button v-if="canWrite" class="button" :disabled="saving || loading">
					{{ __(saving ? "Saving…" : "Save") }}
				</button>
			</div>
		</form>
	</dialog>
</template>
