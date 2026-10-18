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
const dialog = ref(null);
const form = ref(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const partyTypes = ref([]);
const countries = ref([]);
const currencies = ref([]);
const linkedPermissions = reactive({ contact: false, address: false });
const data = reactive({});

function reset() {
	Object.assign(data, {
		party_name: "",
		party_type: "",
		country: "",
		default_currency: "",
		tax_id: "",
		mobile_no: "",
		whatsapp_no: "",
		email_id: "",
		address: "",
	});
	error.value = "";
}

async function loadOptions() {
	loading.value = true;
	try {
		const referenceOptions = isCustomer.value
			? Promise.all([
					call("frappe.client.get_list", {
						doctype: "Territory",
						fields: ["name"],
						filters: { is_group: 0 },
						limit_page_length: 0,
						order_by: "name asc",
					}),
					call("frappe.client.get_list", {
						doctype: "Currency",
						fields: ["name"],
						filters: { enabled: 1 },
						limit_page_length: 0,
						order_by: "name asc",
					}),
				]).then(([territories, customerCurrencies]) => ({
					countries: territories.map(({ name }) => ({ value: name, label: name })),
					currencies: customerCurrencies.map(({ name }) => ({ value: name, label: name })),
				}))
			: call("an_truck.portal_lookups.get_supplier_form_options", {
					company: ctx.company,
				});
		const [metadata, lookups] = await Promise.all([
			call("an_truck.portal_parties.get_options", {
				doctype: props.doctype,
				company: ctx.company,
			}),
			referenceOptions,
		]);
		const typeField = metadata.fields.find((field) => field.name === `${prefix.value}_type`);
		partyTypes.value = (typeField?.options || "").split("\n").filter(Boolean);
		countries.value = lookups.countries || [];
		currencies.value = lookups.currencies || [];
		Object.assign(linkedPermissions, metadata.linked_permissions);
		data.party_type = partyTypes.value[0] || "";
		const companyCurrency = ctx.companies.find(
			(company) => company.name === ctx.company,
		)?.default_currency;
		if (currencies.value.some((option) => option.value === companyCurrency))
			data.default_currency = companyCurrency;
	} catch (e) {
		error.value = e.message;
	} finally {
		loading.value = false;
	}
}

async function open() {
	reset();
	dialog.value?.showModal();
	await Promise.all([loadOptions(), nextTick()]);
	form.value?.querySelector("input")?.focus();
}

function close() {
	if (!saving.value) dialog.value?.close();
}

function validate() {
	if (!data.party_name.trim()) return __(`Please enter a ${prefix.value} name.`);
	if (!isCustomer.value && data.address.trim() && !data.country)
		return __("Please select a country when entering an address.");
	return "";
}

async function save() {
	if (saving.value || loading.value) return;
	error.value = validate();
	if (error.value) {
		form.value?.querySelector(":invalid")?.focus();
		return;
	}
	if (!form.value.reportValidity()) return;
	saving.value = true;
	try {
		const payload = {
			[`${prefix.value}_name`]: data.party_name.trim(),
			[`${prefix.value}_type`]: data.party_type,
			default_currency: data.default_currency,
			tax_id: data.tax_id.trim(),
		};
		// Standard Customer stores its geographic classification in Territory;
		// Supplier has a direct Country field.
		payload[isCustomer.value ? "territory" : "country"] = data.country;
		if (linkedPermissions.contact && (data.mobile_no || data.whatsapp_no || data.email_id)) {
			payload.contact = {
				mobile_no: data.mobile_no.trim(),
				phone: data.whatsapp_no.trim(),
				email_id: data.email_id.trim(),
			};
		}
		if (!isCustomer.value && linkedPermissions.address && data.address.trim()) {
			payload.address = {
				country: data.country,
				address_line1: data.address.trim(),
				address_line2: "",
				city: data.address.trim(),
				pincode: "",
			};
		}
		const result = await call(
			"an_truck.portal_parties.save_party",
			{ doctype: props.doctype, data: payload, company: ctx.company },
			true,
		);
		dialog.value?.close();
		notification.value = __(`${props.doctype} created successfully.`);
		emit("created", result.name);
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
		:aria-label="__(`New ${doctype}`)"
		@cancel.prevent="close"
	>
		<form ref="form" @submit.prevent="save">
			<div class="dialog-head">
				<div>
					<p class="eyebrow">{{ __(doctype === "Customer" ? "Customers" : "Suppliers") }}</p>
					<h2>{{ __(`New ${doctype}`) }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid create-import-grid">
					<FormField
						v-model="data.party_name"
						:label="__(`${doctype} Name`)"
						required
					/>
					<FormField
						v-model="data.party_type"
						:label="__(`${doctype} Type`)"
						type="select"
						:options="partyTypes"
						:loading="loading"
						required
					/>
					<FormField
						v-model="data.country"
						:label="__('Country')"
						type="select"
						:options="countries"
						:loading="loading"
					/>
					<FormField
						v-model="data.default_currency"
						:label="__('Billing Currency')"
						type="select"
						:options="currencies"
						:loading="loading"
						ltr
					/>
					<FormField v-model="data.tax_id" :label="__('Tax ID')" ltr />
					<FormField
						v-model="data.mobile_no"
						:label="__('Mobile Number')"
						type="tel"
						:disabled="!linkedPermissions.contact"
						ltr
					/>
					<FormField
						v-model="data.whatsapp_no"
						:label="__('WhatsApp Number')"
						type="tel"
						:disabled="!linkedPermissions.contact"
						ltr
					/>
					<FormField
						v-model="data.email_id"
						:label="__('Email')"
						type="email"
						:disabled="!linkedPermissions.contact"
						ltr
					/>
					<FormField
						v-if="!isCustomer"
						v-model="data.address"
						class="field-span-full"
						:label="__('Address')"
						type="textarea"
						:disabled="!linkedPermissions.address"
					/>
				</div>
				<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="saving" @click="close">
					{{ __("Cancel") }}
				</button>
				<button class="button" :disabled="saving || loading">
					{{ __(saving ? "Saving…" : "Save") }}
				</button>
			</div>
		</form>
	</dialog>
</template>
