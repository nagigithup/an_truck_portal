<script setup>
import { computed, inject, nextTick, reactive, ref } from "vue";
import { call } from "../api";
import { __ } from "../i18n";
import FormField from "./FormField.vue";

const emit = defineEmits(["saved"]);
const { notification } = inject("portal");
const dialog = ref(null);
const form = ref(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const providerName = ref("");
const modified = ref("");
const canWrite = ref(false);
const countries = ref([]);
const data = reactive({});
const editing = computed(() => Boolean(providerName.value));
const title = computed(() => __(editing.value ? "Edit Provider" : "New Provider"));

function reset() {
	Object.assign(data, {
		provider_name: "",
		commercial_registration: "",
		tax_number: "",
		mobile: "",
		phone: "",
		email: "",
		website: "",
		primary_address: "",
		city: "",
		country: "",
		notes: "",
	});
	providerName.value = "";
	modified.value = "";
	canWrite.value = false;
	countries.value = [];
	error.value = "";
}

async function open(name = "") {
	reset();
	providerName.value = name;
	dialog.value?.showModal();
	dialog.value?.querySelector(".dialog-body")?.scrollTo({ top: 0 });
	loading.value = true;
	try {
		const result = await call("an_truck_portal.api.warranty.get_provider_form", {
			name: name || undefined,
		});
		Object.assign(data, result.record);
		modified.value = result.modified || "";
		canWrite.value = result.can_write;
		countries.value = result.countries || [];
		if (!canWrite.value) error.value = __("You do not have permission to save providers.");
		await nextTick();
		form.value?.querySelector("input")?.focus();
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
	if (!data.provider_name.trim()) return __("Please enter a provider name.");
	return "";
}

async function save() {
	if (saving.value || loading.value || !canWrite.value) return;
	error.value = validate();
	if (error.value) {
		form.value?.querySelector(":invalid")?.focus();
		return;
	}
	if (!form.value.reportValidity()) return;
	saving.value = true;
	try {
		const result = await call(
			"an_truck_portal.api.warranty.save_provider",
			{
				data: { ...data },
				name: providerName.value || undefined,
				modified: modified.value || undefined,
			},
			true,
		);
		dialog.value?.close();
		notification.value = __(
			editing.value ? "Provider updated successfully." : "Provider created successfully.",
		);
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
	<dialog ref="dialog" class="operation-dialog" :aria-label="title" @cancel.prevent="close">
		<form ref="form" @submit.prevent="save">
			<div class="dialog-head">
				<div>
					<p class="eyebrow">{{ __("Warranty Providers") }}</p>
					<h2>{{ title }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">
					×
				</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid create-import-grid">
					<FormField
						v-model="data.provider_name"
						class="field-span-full"
						:label="__('Provider Name')"
						required
						:disabled="loading || !canWrite"
					/>
					<FormField
						v-model="data.commercial_registration"
						:label="__('Commercial Registration / CR')"
						:disabled="loading || !canWrite"
						ltr
					/>
					<FormField
						v-model="data.tax_number"
						:label="__('Tax Number')"
						:disabled="loading || !canWrite"
						ltr
					/>
					<FormField
						v-model="data.mobile"
						:label="__('Mobile')"
						type="tel"
						:disabled="loading || !canWrite"
						ltr
					/>
					<FormField
						v-model="data.phone"
						:label="__('Phone')"
						type="tel"
						:disabled="loading || !canWrite"
						ltr
					/>
					<FormField
						v-model="data.email"
						:label="__('Email')"
						type="email"
						:disabled="loading || !canWrite"
						ltr
					/>
					<FormField
						v-model="data.website"
						:label="__('Website')"
						type="url"
						:disabled="loading || !canWrite"
						ltr
					/>
					<FormField
						v-model="data.primary_address"
						class="field-span-full"
						:label="__('Address')"
						:link="{ doctype: 'Address' }"
						:disabled="loading || !canWrite"
					/>
					<FormField
						v-model="data.city"
						:label="__('City')"
						:disabled="loading || !canWrite"
					/>
					<FormField
						v-model="data.country"
						:label="__('Country')"
						type="select"
						:options="countries"
						:loading="loading"
						:disabled="!canWrite"
					/>
					<FormField
						v-model="data.notes"
						class="field-span-full"
						:label="__('Notes')"
						type="textarea"
						:disabled="loading || !canWrite"
					/>
				</div>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="saving" @click="close">
					{{ __("Cancel") }}
				</button>
				<button class="button" :disabled="saving || loading || !canWrite">
					{{ __(saving ? "Saving…" : "Save") }}
				</button>
			</div>
		</form>
	</dialog>
</template>
