<script setup>
import { computed, inject, nextTick, reactive, ref } from "vue";
import { call } from "../api";
import { __ } from "../i18n";
import FormField from "./FormField.vue";

const props = defineProps({
	doctype: {
		type: String,
		default: "Supplier",
		validator: (value) => ["Customer", "Supplier"].includes(value),
	},
});
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const prefix = computed(() => props.doctype.toLowerCase());
const isCustomer = computed(() => props.doctype === "Customer");
const dialog = ref(null), form = ref(null), loading = ref(false), saving = ref(false);
const error = ref(""), partyTypes = ref([]), countries = ref([]), currencies = ref([]);
const name = ref(null), modified = ref(null), canSave = ref(false), metadata = ref([]);
const originalAddress = ref(""), originalContact = ref("");
const originalParty = ref({});
const linkedPermissions = reactive({ contact: false, address: false });
const data = reactive({}), nationalAddress = reactive({});
const title = computed(() => __(`${name.value ? "Edit" : "New"} ${props.doctype}`));
const hasCR = computed(() => isCustomer.value && metadata.value.some(field => field.name === "commercial_registration_number"));
const hasTerritory = computed(() => isCustomer.value && metadata.value.some(field => field.name === "territory"));
const addressFields = [
	["country", "Country"], ["city", "City"], ["district", "District"], ["street", "Street"],
	["building_number", "Building Number"], ["additional_number", "Additional Number"],
	["pincode", "Postal Code"], ["short_address", "Short Address"],
];
const addressEntered = computed(() => addressFields.some(([key]) => key !== "country" && String(nationalAddress[key] || "").trim()));
const isSaudi = computed(() => ["saudi arabia", "السعودية", "المملكة العربية السعودية"].includes(String(nationalAddress.country || "").trim().toLowerCase()));

function reset(recordName) {
	name.value = recordName || null;
	modified.value = null;
	canSave.value = false;
	Object.assign(linkedPermissions, { contact: false, address: false });
	Object.assign(data, {
		party_name: "", party_type: "", country: "", territory: "",
		default_currency: isCustomer.value && !recordName ? "SAR" : "",
		tax_id: "", commercial_registration_number: "", mobile_no: "", whatsapp_no: "", email_id: "", address: "",
	});
	for (const [key] of addressFields) nationalAddress[key] = key === "country" && isCustomer.value && !recordName ? "Saudi Arabia" : "";
	originalAddress.value = "";
	originalContact.value = "";
	error.value = "";
}

async function loadOptions() {
	const referenceOptions = isCustomer.value
		? Promise.all([
			call("frappe.client.get_list", { doctype: "Country", fields: ["name"], limit_page_length: 0, order_by: "name asc" }),
			call("frappe.client.get_list", { doctype: "Currency", fields: ["name"], filters: { enabled: 1 }, limit_page_length: 0, order_by: "name asc" }),
		]).then(([countryRows, currencyRows]) => ({
			countries: countryRows.map(({ name }) => ({ value: name, label: name })),
			currencies: currencyRows.map(({ name }) => ({ value: name, label: name })),
		}))
		: call("an_truck.portal_lookups.get_supplier_form_options", { company: ctx.company });
	const [options, lookups] = await Promise.all([
		call("an_truck.portal_parties.get_options", { doctype: props.doctype, company: ctx.company }), referenceOptions,
	]);
	metadata.value = options.fields;
	const typeField = options.fields.find(field => field.name === `${prefix.value}_type`);
	partyTypes.value = (typeField?.options || "").split("\n").filter(Boolean);
	countries.value = lookups.countries || [];
	currencies.value = lookups.currencies || [];
	if (!name.value) {
		Object.assign(linkedPermissions, options.linked_permissions);
		canSave.value = options.create;
		data.party_type = partyTypes.value[0] || "";
		if (!isCustomer.value) {
			const currency = ctx.companies.find(company => company.name === ctx.company)?.default_currency;
			if (currencies.value.some(option => option.value === currency)) data.default_currency = currency;
		}
	}
}

function contactValues() {
	return { mobile_no: data.mobile_no.trim(), phone: data.whatsapp_no.trim(), email_id: data.email_id.trim() };
}

function partyValues() {
	const values = {
		[`${prefix.value}_name`]: data.party_name.trim(), [`${prefix.value}_type`]: data.party_type,
		default_currency: data.default_currency, tax_id: data.tax_id.trim(),
	};
	if (!isCustomer.value) values.country = data.country;
	else {
		if (data.territory || name.value) values.territory = data.territory;
		if (hasCR.value) values.commercial_registration_number = data.commercial_registration_number.trim();
	}
	return values;
}

async function open(recordName = null) {
	reset(recordName);
	loading.value = true;
	dialog.value?.showModal();
	try {
		await loadOptions();
		if (name.value) {
			const result = await call("an_truck.portal_parties.get_party", { doctype: props.doctype, name: name.value, company: ctx.company });
			const record = result.record;
			Object.assign(data, {
				party_name: record[`${prefix.value}_name`] || "", party_type: record[`${prefix.value}_type`] || "",
				country: record.country || "", territory: record.territory || "", default_currency: record.default_currency || "",
				tax_id: record.tax_id || "", commercial_registration_number: record.commercial_registration_number || "",
				mobile_no: record.contact?.mobile_no || "", whatsapp_no: record.contact?.phone || "", email_id: record.contact?.email_id || "",
			});
			if (isCustomer.value) for (const [key] of addressFields) nationalAddress[key] = record.address?.[key] ?? "";
			modified.value = result.modified;
			canSave.value = result.can_write;
			Object.assign(linkedPermissions, result.linked_permissions);
		}
		originalAddress.value = JSON.stringify(nationalAddress);
		originalContact.value = JSON.stringify(contactValues());
		originalParty.value = partyValues();
		await nextTick();
		form.value?.querySelector("input")?.focus();
	} catch (e) { error.value = e.message; canSave.value = false; }
	finally { loading.value = false; }
}

function close() { if (!saving.value) dialog.value?.close(); }

function validate() {
	if (!data.party_name.trim()) return __(`Please enter a ${prefix.value} name.`);
	if (!isCustomer.value && data.address.trim() && !data.country) return __("Please select a country when entering an address.");
	if (isCustomer.value && isSaudi.value) {
		for (const [key, pattern, message] of [
			["building_number", /^[0-9]{4}$/, "Building Number must contain exactly 4 digits."],
			["additional_number", /^[0-9]{4}$/, "Additional Number must contain exactly 4 digits."],
			["pincode", /^[0-9]{5}$/, "Postal Code must contain exactly 5 digits."],
			["short_address", /^[A-Za-z]{4}[0-9]{4}$/, "Short Address must contain 4 letters followed by 4 digits."],
		]) if (String(nationalAddress[key] || "").trim() && !pattern.test(String(nationalAddress[key]).trim())) return __(message);
	}
	return "";
}

async function save() {
	if (saving.value || loading.value || !canSave.value) return;
	error.value = validate();
	if (error.value) {
		await nextTick();
		form.value?.querySelector(".form-error")?.scrollIntoView({ block: "nearest" });
		return;
	}
	if (!form.value.reportValidity()) return;
	saving.value = true;
	try {
		const payload = partyValues();
		if (name.value) for (const key of Object.keys(payload)) {
			if (payload[key] === originalParty.value[key]) delete payload[key];
		}
		const contact = contactValues();
		if (linkedPermissions.contact && (name.value ? JSON.stringify(contact) !== originalContact.value : Object.values(contact).some(Boolean))) payload.contact = contact;
		if (isCustomer.value && linkedPermissions.address && (name.value ? JSON.stringify(nationalAddress) !== originalAddress.value : addressEntered.value)) payload.address = { ...nationalAddress };
		if (!isCustomer.value && linkedPermissions.address && data.address.trim()) payload.address = {
			country: data.country, address_line1: data.address.trim(), address_line2: "", city: data.address.trim(), pincode: "",
		};
		const result = await call("an_truck.portal_parties.save_party", {
			doctype: props.doctype, data: payload, name: name.value, modified: modified.value, company: ctx.company,
		}, true);
		dialog.value?.close();
		notification.value = __(`${props.doctype} ${name.value ? "updated" : "created"} successfully.`);
		emit("created", result.name);
	} catch (e) { error.value = e.message; }
	finally { saving.value = false; }
}

defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog" :class="{ 'customer-party-dialog': isCustomer }" :aria-label="title" @cancel.prevent="close">
		<form ref="form" @submit.prevent="save">
			<div class="dialog-head"><div><p class="eyebrow">{{ __(isCustomer ? "Customers" : "Suppliers") }}</p><h2>{{ title }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div>
			<div class="dialog-body">
				<div class="form-grid create-import-grid">
					<FormField v-model="data.party_name" :label="__(`${doctype} Name`)" required :disabled="loading || !canSave" />
					<FormField v-model="data.party_type" :label="__(`${doctype} Type`)" type="select" :options="partyTypes" :loading="loading" required :disabled="!canSave" />
					<FormField v-if="!isCustomer" v-model="data.country" :label="__('Country')" type="select" :options="countries" :loading="loading" />
					<FormField v-model="data.default_currency" :label="__('Billing Currency')" type="select" :options="currencies" :loading="loading" :disabled="!canSave" ltr />
					<FormField v-model="data.tax_id" :label="__(isCustomer ? 'VAT Registration Number' : 'Tax ID')" :disabled="loading || !canSave" ltr />
					<FormField v-if="hasCR" v-model="data.commercial_registration_number" :label="__('Commercial Registration Number')" :disabled="loading || !canSave" ltr />
					<FormField v-if="hasTerritory" v-model="data.territory" :label="__('Territory')" :link="{ doctype, field: 'territory', company: ctx.company }" :disabled="loading || !canSave" />
					<FormField v-model="data.mobile_no" :label="__('Mobile Number')" type="tel" :disabled="loading || !canSave || !linkedPermissions.contact" ltr />
					<FormField v-model="data.whatsapp_no" :label="__('WhatsApp Number')" type="tel" :disabled="loading || !canSave || !linkedPermissions.contact" ltr />
					<FormField v-model="data.email_id" :label="__('Email')" type="email" :disabled="loading || !canSave || !linkedPermissions.contact" ltr />
					<FormField v-if="!isCustomer" v-model="data.address" class="field-span-full" :label="__('Address')" type="textarea" :disabled="!linkedPermissions.address" />
				</div>
				<section v-if="isCustomer" class="national-address-section customer-national-address" aria-labelledby="customer-national-address-title">
					<h3 id="customer-national-address-title">{{ __("National Address") }}</h3>
					<div class="form-grid create-import-grid">
						<FormField v-for="[key, label] in addressFields" :key="key" v-model="nationalAddress[key]" :label="__(label)" :type="key === 'country' ? 'select' : 'text'" :options="key === 'country' ? countries : undefined" :loading="key === 'country' && loading" :required="addressEntered && ['country', 'city', 'street'].includes(key)" :disabled="loading || !canSave || !linkedPermissions.address" :ltr="['building_number', 'additional_number', 'pincode', 'short_address'].includes(key)" />
					</div>
				</section>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" :disabled="saving" @click="close">{{ __("Cancel") }}</button><button class="button" :disabled="saving || loading || !canSave">{{ __(saving ? "Saving…" : "Save") }}</button></div>
		</form>
	</dialog>
</template>

<style scoped>
.customer-party-dialog .dialog-head,
.customer-party-dialog .dialog-actions { flex-shrink: 0; }
.customer-party-dialog .dialog-body { min-height: 0; }
.customer-party-dialog :deep(.form-field > label) { display: block; }
.customer-national-address { margin-top: 22px; padding-top: 18px; }
.customer-national-address h3 { margin: 0 0 16px; font-size: 15px; text-align: start; }
.customer-party-dialog .create-import-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 767px) {
	.customer-party-dialog .create-import-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
