<script setup>
import { computed, inject, ref } from "vue";
import { call, uploadFile, __ } from "../api";
import FormField from "./FormField.vue";

const emit = defineEmits(["saved"]);
const { notification } = inject("portal");
const visible = ref(false);
const state = ref("loading");
const error = ref("");
const payload = ref(null);
const context = ref({});
const vehicleName = ref("");
const initial = ref({});
const form = ref({});
const editing = ref(false);
const requestedEdit = ref(false);
const busy = ref(false);
const attachments = ref({});

// API values are JSON data. Serializing them before storing snapshots strips
// Vue proxies and any accidental function properties that structuredClone
// cannot accept.
function plainData(value) {
	if (value === undefined) return undefined;
	return JSON.parse(
		JSON.stringify(value, (_key, current) =>
			typeof current === "function" ? undefined : current,
		),
	);
}

const allFields = computed(() => payload.value?.sections.flatMap((section) => section.fields) || []);
const fieldValues = computed(() =>
	Object.fromEntries(allFields.value.map((field) => [field.fieldname, field.value])),
);
const detailFields = computed(() => [
	{ label: __("Vehicle Master"), value: payload.value?.name, fieldname: "name", ltr: true },
	{ label: __("Vehicle / Item"), value: fieldValues.value.item_name || fieldValues.value.item_code, fieldname: "item_name" },
	{ label: __("Item Code"), value: fieldValues.value.item_code, fieldname: "item_code", ltr: true },
	{ label: __("Model"), value: fieldValues.value.model, fieldname: "model" },
	{ label: __("Color"), value: fieldValues.value.color, fieldname: "color" },
	{ label: __("Production Year"), value: fieldValues.value.model_year, fieldname: "model_year" },
	{ label: __("Supplier"), value: fieldValues.value.supplier, fieldname: "supplier" },
	{ label: __("Purchase Cost"), value: fieldValues.value.purchase_valuation_rate, fieldname: "purchase_valuation_rate" },
	{ label: __("Landed Cost Added"), value: fieldValues.value.landed_cost_added, fieldname: "landed_cost_added" },
	{ label: __("Landed Cost"), value: fieldValues.value.final_valuation_rate, fieldname: "final_valuation_rate" },
	{ label: __("Purchase Receipt"), value: fieldValues.value.purchase_receipt, fieldname: "purchase_receipt", ltr: true },
	{ label: __("Import File"), value: fieldValues.value.vehicle_import_file, fieldname: "vehicle_import_file", ltr: true },
	{ label: __("Inspection Status"), value: context.value.inspection_status, fieldname: "inspection_status" },
	{ label: __("Warranty Status"), value: context.value.warranty?.status, fieldname: "warranty" },
	{ label: __("Sales Status"), value: context.value.sales_status, fieldname: "sales_status" },
	{ label: __("Current Location"), value: fieldValues.value.warehouse, fieldname: "warehouse" },
]);

function inputType(field) {
	if (["Int", "Float", "Currency", "Percent"].includes(field.fieldtype)) return "number";
	if (field.fieldtype === "Date") return "date";
	if (field.fieldtype === "Datetime") return "datetime-local";
	if (["Small Text", "Long Text", "Text", "Text Editor", "Code"].includes(field.fieldtype)) return "textarea";
	if (field.fieldtype === "Select") return "select";
	return "text";
}

function fieldOptions(field) {
	return (field.choices || []).map((choice) => ({
		value: choice.value ?? choice,
		label: choice.label ?? __(choice),
	}));
}

function linkConfig(field) {
	return field.fieldtype === "Link" && field.options ? { doctype: field.options } : null;
}

function formatValue(value, fieldname) {
	if (value == null || value === "") return "—";
	if (["inspection_status", "warranty", "sales_status", "vehicle_status"].includes(fieldname)) {
		return __(value);
	}
	if (["purchase_valuation_rate", "landed_cost_added", "final_valuation_rate"].includes(fieldname)) {
		try {
			return new Intl.NumberFormat(document.documentElement.lang, {
				style: "currency",
				currency: fieldValues.value.cost_currency || "SAR",
				maximumFractionDigits: 2,
			}).format(Number(value));
		} catch {}
	}
	return value;
}

async function load(vehicleMaster, requestEdit = false) {
	requestedEdit.value = requestEdit;
	state.value = "loading";
	error.value = "";
	payload.value = null;
	form.value = {};
	initial.value = {};
	attachments.value = {};
	editing.value = false;
	try {
		const result = await call("an_truck_portal.api.records.get_vehicle_form", {
			vehicle_master: vehicleMaster,
		});
		const values = Object.fromEntries(
			result.sections.flatMap((section) =>
				section.fields.map((field) => [
					field.fieldname,
					["Table", "Table MultiSelect"].includes(field.fieldtype)
						? plainData(field.value || [])
						: field.value ?? "",
				]),
			),
		);
		payload.value = result;
		form.value = values;
		initial.value = plainData(values);
		editing.value = requestEdit && result.can_edit;
		state.value = "ready";
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
		state.value = "error";
	}
}

async function open(vehicle, requestEdit = false) {
	visible.value = true;
	const name = typeof vehicle === "string" ? vehicle : vehicle.name;
	vehicleName.value = name;
	context.value = typeof vehicle === "string" ? {} : plainData(vehicle);
	await load(name, requestEdit);
}

function close() {
	if (!busy.value) visible.value = false;
}

function cancelEdit() {
	form.value = plainData(initial.value);
	attachments.value = {};
	editing.value = false;
	error.value = "";
}

function chooseAttachment(field, event) {
	attachments.value[field.fieldname] = event.target.files?.[0] || null;
}

function addRow(field) {
	form.value[field.fieldname].push(
		Object.fromEntries((field.child_fields || []).map((child) => [child.fieldname, ""])),
	);
}

async function save() {
	if (busy.value || !payload.value?.can_edit) return;
	busy.value = true;
	error.value = "";
	try {
		await call(
			"an_truck_portal.api.records.update_vehicle",
			{ vehicle_master: payload.value.name, values: form.value },
			true,
		);
		for (const [fieldname, file] of Object.entries(attachments.value)) {
			if (!file) continue;
			await uploadFile(file, "Vehicle Master", payload.value.name, {
				method: "an_truck_portal.api.records.upload_vehicle_attachment",
				fields: { vehicle_master: payload.value.name, fieldname },
			});
		}
		const name = payload.value.name;
		await load(name, false);
		notification.value = __("Vehicle information updated successfully.");
		emit("saved", { name });
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = false;
	}
}

defineExpose({ open });
</script>

<template>
	<div v-if="visible" class="drawer-backdrop" @click.self="close">
		<aside class="vehicle-drawer vehicle-editor-drawer" role="dialog" aria-modal="true" :aria-label="__('Vehicle Details')">
			<div class="drawer-head">
				<div><p class="eyebrow">{{ editing ? __("Edit Vehicle") : __("Vehicle Details") }}</p><h2 class="ltr">{{ payload?.vin || context.vin || vehicleName || "—" }}</h2></div>
				<div class="drawer-actions">
					<button v-if="state === 'ready' && !editing && payload.can_edit" type="button" class="button secondary small" @click="editing = true">{{ __("Edit") }}</button>
					<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
				</div>
			</div>
			<div v-if="state === 'loading'" class="empty">{{ __("Loading…") }}</div>
			<div v-else-if="state === 'error'" class="empty error" role="alert">
				<p>{{ __(error) }}</p>
				<button type="button" class="button secondary small" @click="load(vehicleName, requestedEdit)">{{ __("Retry") }}</button>
			</div>
			<template v-else-if="!editing">
				<div class="drawer-body">
					<div v-for="field in detailFields" :key="field.fieldname"><small>{{ field.label }}</small><b :class="{ ltr: field.ltr }">{{ formatValue(field.value, field.fieldname) }}</b></div>
				</div>
				<p v-if="payload.completed_import_file" class="readonly-note">{{ __("This Vehicle Import File is completed and is read-only in AN Truck Portal.") }}</p>
			</template>
			<form v-else class="vehicle-full-form" @submit.prevent="save">
				<section v-for="section in payload.sections" :key="section.label" class="vehicle-form-section">
					<h3>{{ section.label }}</h3>
					<div class="vehicle-form-grid">
						<template v-for="field in section.fields" :key="field.fieldname">
							<div v-if="field.fieldtype === 'Check'" class="form-field checkbox-field">
								<label><input v-model="form[field.fieldname]" type="checkbox" true-value="1" false-value="0" :disabled="field.read_only" /> {{ field.label }}</label>
							</div>
							<div v-else-if="['Attach', 'Attach Image'].includes(field.fieldtype)" class="form-field attachment-field">
								<label>{{ field.label }}</label><a v-if="form[field.fieldname]" :href="form[field.fieldname]" target="_blank" rel="noopener">{{ __("View current attachment") }}</a><input v-if="!field.read_only" type="file" :accept="field.fieldtype === 'Attach Image' ? 'image/*' : undefined" @change="chooseAttachment(field, $event)" />
							</div>
							<div v-else-if="['Table', 'Table MultiSelect'].includes(field.fieldtype)" class="vehicle-child-table">
								<div class="dialog-section-head"><h4>{{ field.label }}</h4><button v-if="!field.read_only" type="button" class="button secondary small" @click="addRow(field)">{{ __("+ Add Row") }}</button></div>
								<div v-for="(row, rowIndex) in form[field.fieldname]" :key="rowIndex" class="vehicle-child-row">
									<FormField v-for="child in field.child_fields" :key="child.fieldname" v-model="row[child.fieldname]" :label="child.label" :type="inputType(child)" :required="child.required" :disabled="field.read_only || child.read_only" :options="fieldOptions(child)" :link="linkConfig(child)" :step="['Float','Currency','Percent'].includes(child.fieldtype) ? 'any' : undefined" />
									<button v-if="!field.read_only" type="button" class="remove-row" :aria-label="__('Delete')" @click="form[field.fieldname].splice(rowIndex, 1)">×</button>
								</div>
								<div v-if="!form[field.fieldname].length" class="empty compact">{{ __("No rows added.") }}</div>
							</div>
							<FormField v-else v-model="form[field.fieldname]" :label="field.label" :type="inputType(field)" :required="field.required" :disabled="field.read_only" :options="fieldOptions(field)" :link="linkConfig(field)" :min="['Int','Float','Currency','Percent'].includes(field.fieldtype) ? 0 : undefined" :step="['Float','Currency','Percent'].includes(field.fieldtype) ? 'any' : undefined" />
						</template>
					</div>
				</section>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
				<div class="drawer-edit-actions vehicle-form-actions"><button type="button" class="button secondary" :disabled="busy" @click="cancelEdit">{{ __("Cancel") }}</button><button class="button" :disabled="busy">{{ busy ? __("Saving…") : __("Save Vehicle") }}</button></div>
			</form>
		</aside>
	</div>
</template>
