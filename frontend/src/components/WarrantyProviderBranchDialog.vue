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
const branchName = ref("");
const modified = ref("");
const canWrite = ref(false);
const editRequested = ref(false);
const data = reactive({});
const existing = computed(() => Boolean(branchName.value));
const editable = computed(() => !existing.value || editRequested.value);
const title = computed(() => {
	if (!existing.value) return __("Add Branch");
	return __(editRequested.value ? "Edit Branch" : "View Branch");
});
const fieldsDisabled = computed(
	() => loading.value || !editable.value || !canWrite.value,
);

function reset() {
	Object.assign(data, {
		branch_name: "",
		address: "",
		city: "",
		google_maps_url: "",
		contact_person: "",
		mobile: "",
		email: "",
		working_hours: "",
	});
	providerName.value = "";
	branchName.value = "";
	modified.value = "";
	canWrite.value = false;
	editRequested.value = false;
	error.value = "";
}

async function open(provider, name = "", edit = false) {
	reset();
	providerName.value = provider;
	branchName.value = name;
	editRequested.value = !name || edit;
	dialog.value?.showModal();
	dialog.value?.querySelector(".dialog-body")?.scrollTo({ top: 0 });
	loading.value = true;
	try {
		const result = await call("an_truck_portal.api.warranty.get_provider_branch_form", {
			provider,
			name: name || undefined,
		});
		Object.assign(data, result.record);
		modified.value = result.modified || "";
		canWrite.value = result.can_write;
		if (editable.value && !canWrite.value) {
			error.value = __("You do not have permission to save branches.");
		}
		await nextTick();
		if (editable.value && canWrite.value) form.value?.querySelector("input")?.focus();
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
	if (!data.branch_name.trim()) return __("Please enter a branch name.");
	if (!data.city.trim()) return __("Please enter a city.");
	return "";
}

async function save() {
	if (saving.value || loading.value || !editable.value || !canWrite.value) return;
	error.value = validate();
	if (error.value) {
		form.value?.querySelector(":invalid")?.focus();
		return;
	}
	if (!form.value.reportValidity()) return;
	saving.value = true;
	try {
		const result = await call(
			"an_truck_portal.api.warranty.save_provider_branch",
			{
				provider: providerName.value,
				data: { ...data },
				name: branchName.value || undefined,
				modified: modified.value || undefined,
			},
			true,
		);
		dialog.value?.close();
		notification.value = __(
			existing.value ? "Branch updated successfully." : "Branch created successfully.",
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
					<p class="eyebrow">{{ __("Branches") }}</p>
					<h2>{{ title }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid create-import-grid">
					<FormField
						v-model="data.branch_name"
						class="field-span-full"
						:label="__('Branch Name')"
						required
						:disabled="fieldsDisabled"
					/>
					<FormField
						v-model="data.address"
						:label="__('Address')"
						:link="{ doctype: 'Address' }"
						:disabled="fieldsDisabled"
					/>
					<FormField
						v-model="data.city"
						:label="__('City')"
						required
						:disabled="fieldsDisabled"
					/>
					<FormField
						v-model="data.google_maps_url"
						:label="__('Google Maps URL')"
						type="url"
						:disabled="fieldsDisabled"
						ltr
					/>
					<FormField
						v-model="data.contact_person"
						:label="__('Contact Person')"
						:disabled="fieldsDisabled"
					/>
					<FormField
						v-model="data.mobile"
						:label="__('Mobile')"
						type="tel"
						:disabled="fieldsDisabled"
						ltr
					/>
					<FormField
						v-model="data.email"
						:label="__('Email')"
						type="email"
						:disabled="fieldsDisabled"
						ltr
					/>
					<FormField
						v-model="data.working_hours"
						class="field-span-full"
						:label="__('Working Hours')"
						type="textarea"
						:disabled="fieldsDisabled"
					/>
				</div>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="saving" @click="close">
					{{ __(editable ? "Cancel" : "Close") }}
				</button>
				<button
					v-if="editable"
					class="button"
					:disabled="saving || loading || !canWrite"
				>
					{{ __(saving ? "Saving…" : "Save") }}
				</button>
			</div>
		</form>
	</dialog>
</template>
