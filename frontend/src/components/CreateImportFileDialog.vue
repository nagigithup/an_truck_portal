<script setup>
import { inject, nextTick, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { call } from "../api";
import { __ } from "../i18n";
import FormField from "./FormField.vue";
import CreateSupplierDialog from "./CreateSupplierDialog.vue";

const { ctx, notification } = inject("portal");
const router = useRouter();
const dialog = ref(null);
const form = ref(null);
const supplierField = ref(null);
const supplierDialog = ref(null);
const saving = ref(false);
const error = ref("");
const data = reactive({});

function reset() {
	Object.assign(data, {
		import_title: "",
		supplier: "",
		total_expected_vehicles: "",
		expected_shipping_date: "",
		notes: "",
		country_of_origin: "China",
	});
	error.value = "";
}

async function open() {
	reset();
	dialog.value?.showModal();
	await nextTick();
	form.value?.querySelector("input")?.focus();
}

function close() {
	if (!saving.value) dialog.value?.close();
}

async function supplierCreated(name) {
	data.supplier = name;
	await nextTick();
	await supplierField.value?.refresh();
}

function validate() {
	if (!ctx.company) return __("Select a company from the header before creating an import file.");
	if (!data.import_title.trim()) return __("Please enter an import title.");
	if (!data.supplier.trim()) return __("Please select a supplier.");
	if (data.total_expected_vehicles !== "" && Number(data.total_expected_vehicles) < 0)
		return __("Expected vehicles cannot be negative.");
	return "";
}

async function supplierCurrency() {
	const result = await call("frappe.client.get_value", {
		doctype: "Supplier",
		filters: { name: data.supplier.trim() },
		fieldname: "default_currency",
	});
	return (
		result?.default_currency ||
		ctx.companies.find((company) => company.name === ctx.company)?.default_currency ||
		""
	);
}

async function save() {
	if (saving.value) return;
	error.value = validate();
	if (error.value) {
		form.value?.querySelector(":invalid")?.focus();
		return;
	}
	if (!form.value.reportValidity()) return;
	saving.value = true;
	try {
		const currency = await supplierCurrency();
		if (!currency)
			throw Error(
				__(
					"The selected supplier does not have a currency, and the current company has no default currency.",
				),
			);
		const doc = {
			doctype: "Vehicle Import File",
			company: ctx.company,
			import_title: data.import_title.trim(),
			supplier: data.supplier.trim(),
			supplier_currency: currency,
		};
		for (const field of [
			"total_expected_vehicles",
			"expected_shipping_date",
			"notes",
			"country_of_origin",
		]) {
			if (data[field] !== "") doc[field] = data[field];
		}
		const result = await call("frappe.client.insert", { doc }, true);
		dialog.value?.close();
		notification.value = "Vehicle Import File created successfully.";
		await router.push({ name: "import-workspace", params: { name: result.name } });
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
		:aria-label="__('Create Vehicle File')"
		@cancel.prevent="close"
	>
		<form ref="form" @submit.prevent="save">
			<div class="dialog-head">
				<div>
					<p class="eyebrow">{{ __("Import Management") }}</p>
					<h2>{{ __("Create Vehicle File") }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid create-import-grid">
					<FormField
						v-model="data.import_title"
						:label="__('Import Title')"
						required
					/>
					<div class="supplier-field-with-action">
						<FormField
							ref="supplierField"
							v-model="data.supplier"
							:label="__('Supplier')"
							:link="{ doctype: 'Supplier' }"
							required
						/>
						<button
							type="button"
							class="text-button field-action"
							@click="supplierDialog.open()"
						>
							{{ __("Add Supplier") }}
						</button>
					</div>
					<FormField
						v-model="data.total_expected_vehicles"
						:label="__('Expected Vehicles')"
						type="number"
						:min="0"
						ltr
					/>
					<FormField
						v-model="data.expected_shipping_date"
						:label="__('Expected Shipping Date')"
						type="date"
						ltr
					/>
					<FormField
						v-model="data.notes"
						class="field-span-full"
						:label="__('Notes')"
						type="textarea"
					/>
					<FormField
						v-model="data.country_of_origin"
						:label="__('Country of Origin')"
						:link="{ doctype: 'Country' }"
					/>
				</div>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="saving" @click="close">
					{{ __("Cancel") }}
				</button>
				<button class="button" :disabled="saving">
					{{ __(saving ? "Saving…" : "Save") }}
				</button>
			</div>
		</form>
	</dialog>
	<CreateSupplierDialog ref="supplierDialog" @created="supplierCreated" />
</template>
