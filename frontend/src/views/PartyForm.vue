<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, useId } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { call } from "../api";
import { __ } from "../i18n";
import PageHeader from "../components/PageHeader.vue";
import AppButton from "../components/AppButton.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import LoadingState from "../components/LoadingState.vue";
import EmptyState from "../components/EmptyState.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import { useFormOptions } from "../composables/useFormOptions";
const props = defineProps({ resource: String, name: String });
const formId = useId();
const { ctx, leaveGuard, notification } = inject("portal"),
	route = useRoute(),
	router = useRouter();
const doctype = computed(() => (props.resource === "customers" ? "Customer" : "Supplier")),
	prefix = computed(() => doctype.value.toLowerCase()),
	isNew = computed(() => !props.name);
const fields = ref([]),
	data = ref({ contact: {}, address: {} }),
	initial = ref(""),
	modified = ref(""),
	loading = ref(true),
	error = ref(""),
	saving = ref(false),
	canWrite = ref(false),
	editing = ref(isNew.value || route.query.edit === "1"),
	confirm = ref(null),
	form = ref(null);
const readOnly = computed(() => !editing.value || !canWrite.value);
const dirty = computed(() => !!initial.value && JSON.stringify(data.value) !== initial.value);
const title = computed(() =>
	isNew.value
		? __(`New ${doctype.value}`)
		: editing.value && canWrite.value
			? __(`Edit ${doctype.value}`)
			: data.value[`${prefix.value}_name`],
);
const basic = computed(() =>
	[
		`${prefix.value}_name`,
		`${prefix.value}_type`,
		`${prefix.value}_group`,
		"territory",
		"country",
		"disabled",
		"default_currency",
		...(doctype.value === "Customer" ? ["tax_id"] : []),
		"commercial_registration_number",
		"custom_commercial_registration_number",
		...(doctype.value === "Supplier" ? ["tax_id"] : []),
	]
		.map((name) => fields.value.find((field) => field.name === name))
		.filter(Boolean),
);
const notes = computed(() => fields.value.find((f) => f.name === `${prefix.value}_details`));
const addressRequired = computed(() => Object.values(data.value.address).some(Boolean));
const linkedPermissions = ref({ contact: false, address: false });
const supplierOptions = useFormOptions(
	"an_truck.portal_lookups.get_supplier_form_options",
	() => ({ company: ctx.company }),
);
const { loading: optionsLoading, error: optionsError } = supplierOptions;
const lookupFields = {
	supplier_group: "supplier_groups",
	country: "countries",
	default_currency: "currencies",
	address_country: "countries",
};
function isLookup(name) {
	return doctype.value === "Supplier" && name in lookupFields;
}
function referenceOptions(name) {
	return supplierOptions.data.value[lookupFields[name]] || [];
}
function fieldType(field) {
	return isLookup(field.name) || field.type === "Select" || field.name === "disabled"
		? "select"
		: "text";
}
function options(field) {
	if (isLookup(field.name)) return referenceOptions(field.name);
	return field.name === "disabled"
		? [
				{ value: 0, label: "Active" },
				{ value: 1, label: "Disabled" },
			]
		: (field.options || "").split("\n").filter(Boolean);
}
function link(field) {
	if (isLookup(field.name)) return undefined;
	return field.type === "Link"
		? { doctype: doctype.value, field: field.name, company: ctx.company }
		: undefined;
}
async function load() {
	loading.value = true;
	error.value = "";
	try {
		const metadata = await call("an_truck.portal_parties.get_options", {
			doctype: doctype.value,
			company: ctx.company,
		});
		fields.value = metadata.fields;
		if (isNew.value) {
			canWrite.value = metadata.create;
			linkedPermissions.value = metadata.linked_permissions;
			data.value = Object.fromEntries(
				metadata.fields.map((f) => [
					f.name,
					f.name === "disabled" ? 0 : f.name.endsWith("_type") ? "Company" : "",
				]),
			);
			data.value.contact = { first_name: "", email_id: "", mobile_no: "", phone: "" };
			data.value.address = {
				country: "",
				city: "",
				address_line1: "",
				address_line2: "",
				pincode: "",
			};
		} else {
			const result = await call("an_truck.portal_parties.get_party", {
				doctype: doctype.value,
				name: props.name,
				company: ctx.company,
			});
			data.value = result.record;
			modified.value = result.modified;
			canWrite.value = result.can_write;
			linkedPermissions.value = result.linked_permissions;
		}
		initial.value = JSON.stringify(data.value);
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
}
async function beforeLeave() {
	return !dirty.value || (await confirm.value.ask());
}
onBeforeRouteLeave(beforeLeave);
function unload(event) {
	if (dirty.value) {
		event.preventDefault();
		event.returnValue = "";
	}
}
onMounted(() => {
	leaveGuard.value = beforeLeave;
	window.addEventListener("beforeunload", unload);
	load();
	if (doctype.value === "Supplier") supplierOptions.load();
});
onBeforeUnmount(() => {
	if (leaveGuard.value === beforeLeave) leaveGuard.value = null;
	window.removeEventListener("beforeunload", unload);
});
async function save(andNew = false) {
	if (saving.value || readOnly.value || !form.value.reportValidity()) return;
	saving.value = true;
	error.value = "";
	try {
		const payload = JSON.parse(JSON.stringify(data.value)),
			original = JSON.parse(initial.value);
		for (const kind of ["contact", "address"])
			if (JSON.stringify(payload[kind]) === JSON.stringify(original[kind]))
				delete payload[kind];
		const result = await call(
			"an_truck.portal_parties.save_party",
			{
				doctype: doctype.value,
				data: payload,
				name: props.name,
				modified: modified.value,
				company: ctx.company,
			},
			true,
		);
		initial.value = JSON.stringify(data.value);
		notification.value = `${doctype.value} ${isNew.value ? "created" : "updated"} successfully.`;
		if (andNew && isNew.value) {
			await load();
			form.value?.querySelector("input")?.focus();
		} else {
			const target = andNew
				? `/${props.resource}/new`
				: `/${props.resource}/${encodeURIComponent(result.name)}`;
			if (route.fullPath === target) {
				editing.value = false;
				await load();
			} else await router.push(target);
		}
	} catch (e) {
		error.value = e.message;
	} finally {
		saving.value = false;
	}
}
</script>
<template>
	<div class="page party-entry">
		<LoadingState v-if="loading" /><EmptyState v-else-if="!initial" :message="__(error)" error
			><AppButton @click="load">{{ __("Retry") }}</AppButton></EmptyState
		><template v-else>
			<PageHeader class="entry-header" :title="title">
				<template v-if="!readOnly">
					<router-link class="text-button" :to="`/${resource}`">{{
						__("Cancel")
					}}</router-link>
					<AppButton
						v-if="ctx.permissions[doctype]?.create"
						variant="secondary"
						:busy="saving"
						@click="save(true)"
						>{{ __("Save and New") }}</AppButton
					>
					<AppButton type="submit" :form="formId" :busy="saving">{{
						__(saving ? "Saving…" : "Save")
					}}</AppButton>
				</template>
				<router-link v-else class="text-button" :to="`/${resource}`">{{
					__("Close")
				}}</router-link
				><AppButton v-if="!editing && canWrite" @click="editing = true">{{
					__("Edit")
				}}</AppButton></PageHeader
			>
			<p v-if="error" class="notice error-notice" role="alert">{{ __(error) }}</p>
			<div v-if="optionsError" class="notice error-notice" role="alert">
				<span>{{ __(optionsError) }}</span>
				<AppButton variant="secondary" @click="supplierOptions.load">{{
					__("Retry")
				}}</AppButton>
			</div>
			<form :id="formId" ref="form" @submit.prevent="save(false)">
				<fieldset class="form-body" :disabled="saving">
					<FormSection :title="__('Basic Information')"
						><FormField
							v-for="field in basic"
							:key="field.name"
							v-model="data[field.name]"
							:label="
								__(
									field.name === 'disabled'
										? 'Status'
										: field.name.includes('commercial_registration')
											? 'Commercial Registration Number'
											: field.label,
								)
							"
							:type="fieldType(field)"
							:options="options(field)"
							:loading="isLookup(field.name) && optionsLoading"
							:link="link(field)"
							:ltr="
								[
									'tax_id',
									'default_currency',
									'commercial_registration_number',
									'custom_commercial_registration_number',
								].includes(field.name)
							"
							:required="field.required"
							:disabled="
								readOnly ||
								field.read_only ||
								(isLookup(field.name) && !!optionsError)
							"
					/></FormSection>
					<FormSection :title="__('Contact Information')"
						><FormField
							v-model="data.contact.first_name"
							:label="__('Contact Person')"
							:disabled="readOnly || !linkedPermissions.contact" /><FormField
							v-model="data.contact.mobile_no"
							:label="__('Mobile Number')"
							type="tel"
							ltr
							:disabled="readOnly || !linkedPermissions.contact" /><FormField
							v-model="data.contact.phone"
							:label="__('Phone')"
							type="tel"
							ltr
							:disabled="readOnly || !linkedPermissions.contact" /><FormField
							v-model="data.contact.email_id"
							:label="__('Email')"
							type="email"
							ltr
							:disabled="readOnly || !linkedPermissions.contact"
					/></FormSection>
					<FormSection :title="__('Address')"
						><FormField
							v-model="data.address.country"
							:label="__('Country')"
							:type="isLookup('address_country') ? 'select' : 'text'"
							:options="referenceOptions('address_country')"
							:loading="isLookup('address_country') && optionsLoading"
							:link="
								isLookup('address_country')
									? undefined
									: { doctype, field: 'address_country', company: ctx.company }
							"
							:required="addressRequired"
							:disabled="
								readOnly ||
								!linkedPermissions.address ||
								(isLookup('address_country') && !!optionsError)
							" /><FormField
							v-model="data.address.city"
							:label="__('City')"
							:required="addressRequired"
							:disabled="readOnly || !linkedPermissions.address" /><FormField
							v-model="data.address.pincode"
							:label="__('Postal Code')"
							:disabled="readOnly || !linkedPermissions.address"
							ltr /><FormField
							v-model="data.address.address_line1"
							:label="__('Address Line 1')"
							:required="addressRequired"
							:disabled="readOnly || !linkedPermissions.address" /><FormField
							v-model="data.address.address_line2"
							class="field-span-2"
							:label="__('Address Line 2')"
							:disabled="readOnly || !linkedPermissions.address"
					/></FormSection>
					<FormSection v-if="notes" :title="__('Notes')"
						><FormField
							v-model="data[notes.name]"
							class="field-span-full"
							:label="__('Notes')"
							type="textarea"
							:disabled="readOnly || notes.read_only"
					/></FormSection>
				</fieldset>
			</form> </template
		><ConfirmDialog ref="confirm" />
	</div>
</template>
