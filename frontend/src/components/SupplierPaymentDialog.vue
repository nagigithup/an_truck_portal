<script setup>
import { computed, inject, ref } from "vue";
import { call, uploadFile, __ } from "../api";

const props = defineProps({
	purchaseInvoice: { type: String, default: "" },
	salesInvoice: { type: String, default: "" },
	customer: { type: String, default: "" },
	allowedInvoices: { type: Array, default: null },
});
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null);
const busy = ref(false);
const error = ref("");
const source = ref(null);
const form = ref({});
const attachment = ref(null);
const creationResult = ref(null);
const creationReported = ref(false);
const attachmentUploaded = ref(false);
const operationKey = ref("");
const invoices = ref([]);
const selectedInvoice = ref("");
const runtimeInvoice = ref("");

const isCustomerPayment = computed(() => !props.purchaseInvoice);
const invoiceDoctype = computed(() => (isCustomerPayment.value ? "Sales Invoice" : "Purchase Invoice"));
const hasFixedInvoice = computed(() => !!props.purchaseInvoice || !!props.salesInvoice || !!runtimeInvoice.value);

const selectedMode = computed(() =>
	(source.value?.modes_of_payment || []).find((mode) => mode.name === form.value.mode_of_payment),
);
const referenceRequired = computed(() => !!selectedMode.value?.requires_reference);

function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

async function open(invoice = "") {
	error.value = "";
	busy.value = false;
	source.value = null;
	attachment.value = null;
	creationResult.value = null;
	creationReported.value = false;
	attachmentUploaded.value = false;
	operationKey.value = key();
	form.value = {};
	invoices.value = [];
	runtimeInvoice.value = invoice;
	selectedInvoice.value = invoice || props.salesInvoice || props.purchaseInvoice;
	dialog.value?.showModal();
	try {
		if (!hasFixedInvoice.value) {
			const result = await call("an_truck_portal.api.records.list_records", {
				doctype: "Sales Invoice",
				company: ctx.company,
				page_length: 100,
				filters: {
					docstatus: 1,
					outstanding_amount: [">", 0],
					...(props.customer ? { customer: props.customer } : {}),
				},
			});
			invoices.value = props.allowedInvoices
				? (result.rows || []).filter((row) => props.allowedInvoices.includes(row.name))
				: (result.rows || []);
			selectedInvoice.value = invoices.value.length === 1 ? invoices.value[0].name : "";
		}
		if (selectedInvoice.value) await loadSource();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	}
}

async function loadSource() {
	source.value = await call(
		isCustomerPayment.value
			? "an_truck_portal.api.sales.get_customer_payment_form"
			: "an_truck_portal.api.import_file.get_supplier_payment_form",
		isCustomerPayment.value
			? { sales_invoice: selectedInvoice.value }
			: { purchase_invoice: selectedInvoice.value },
	);
	const defaultMode = source.value.modes_of_payment.find(
		(mode) => mode.name === source.value.mode_of_payment,
	);
	form.value = {
		payment_date: source.value.payment_date,
		mode_of_payment: source.value.mode_of_payment,
		amount: source.value.outstanding_amount,
		reference_number: "",
		reference_date: defaultMode?.requires_reference ? source.value.reference_date : "",
		notes: "",
	};
}

async function changeInvoice() {
	error.value = "";
	source.value = null;
	try {
		if (selectedInvoice.value) await loadSource();
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	}
}

function close() {
	if (!busy.value) dialog.value?.close();
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

function modeChanged() {
	if (referenceRequired.value && !form.value.reference_date) {
		form.value.reference_date = form.value.payment_date || source.value.reference_date;
	}
}

async function save() {
	if (busy.value || !source.value) return;
	const paymentAmount = Number(form.value.amount);
	if (!form.value.mode_of_payment) {
		error.value = __("Mode of Payment is required.");
		return;
	}
	if (!(paymentAmount > 0) || paymentAmount > Number(source.value.outstanding_amount)) {
		error.value = __("Payment amount must be greater than zero and cannot exceed the outstanding amount.");
		return;
	}
	if (referenceRequired.value && (!form.value.reference_number || !form.value.reference_date)) {
		error.value = __("Reference Number and Reference Date are required for bank payments.");
		return;
	}
	busy.value = true;
	error.value = "";
	try {
		if (!creationResult.value) {
			creationResult.value = await call(
				isCustomerPayment.value
					? "an_truck_portal.api.sales.record_customer_payment"
					: "an_truck_portal.api.import_file.record_supplier_payment",
				{
					[isCustomerPayment.value ? "sales_invoice" : "purchase_invoice"]:
						selectedInvoice.value,
					data: form.value,
					idempotency_key: operationKey.value,
				},
				true,
			);
		}
		if (attachment.value && !attachmentUploaded.value) {
			await uploadFile(attachment.value, "Payment Entry", creationResult.value.name, {
				method: isCustomerPayment.value
					? "an_truck_portal.api.sales.upload_customer_payment_attachment"
					: "an_truck_portal.api.import_file.upload_supplier_payment_attachment",
				fields: {
					payment_entry: creationResult.value.name,
					[isCustomerPayment.value ? "sales_invoice" : "purchase_invoice"]:
						selectedInvoice.value,
				},
			});
			attachmentUploaded.value = true;
		}
		if (!creationReported.value) {
			creationReported.value = true;
			emit("created", creationResult.value);
		}
		dialog.value?.close();
		notification.value = __("Payment recorded successfully: {0}", [creationResult.value.name]);
	} catch (e) {
		error.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = false;
	}
}

defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog" :aria-label="__('Record Payment')" @cancel.prevent="close">
		<form @submit.prevent="save">
			<div class="dialog-head">
				<div><p class="eyebrow">{{ __(isCustomerPayment ? "Sales" : "Purchasing") }}</p><h2>{{ __("Record Payment") }}</h2></div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div class="form-grid">
					<label v-if="!hasFixedInvoice" class="wide"><span>{{ __(invoiceDoctype) }}</span><select v-model="selectedInvoice" required :disabled="!!creationResult" @change="changeInvoice"><option value="">{{ __("Select") }}</option><option v-for="invoice in invoices" :key="invoice.name" :value="invoice.name">{{ invoice.name }} · {{ invoice.customer_name || invoice.customer }}</option></select></label>
					<label class="wide"><span>{{ __(isCustomerPayment ? "Customer" : "Supplier") }}</span><input :value="isCustomerPayment ? source?.customer_name || source?.customer : source?.supplier_name || source?.supplier" disabled /></label>
					<label><span>{{ __("Payment Date") }}</span><input v-model="form.payment_date" type="date" required :disabled="!!creationResult" /></label>
					<label>
						<span>{{ __("Mode of Payment") }}</span>
						<select v-model="form.mode_of_payment" required :disabled="!!creationResult" @change="modeChanged">
							<option value="">{{ __("Select") }}</option>
							<option v-for="mode in source?.modes_of_payment || []" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
						</select>
					</label>
					<label><span>{{ __("Amount") }} ({{ source?.currency }})</span><input v-model.number="form.amount" type="number" min="0" :max="source?.outstanding_amount" step="any" required :disabled="!!creationResult" /></label>
					<label><span>{{ __("Reference Number") }}</span><input v-model="form.reference_number" :required="referenceRequired" :disabled="!!creationResult" /></label>
					<label><span>{{ __("Reference Date") }}</span><input v-model="form.reference_date" type="date" :required="referenceRequired" :disabled="!!creationResult" /></label>
					<label class="wide document-attachment">
						<span>{{ __("Payment Receipt Attachment") }}</span>
						<input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" :disabled="attachmentUploaded" @change="chooseAttachment" />
						<small>{{ __("Supported files: PDF, JPG, PNG, WebP") }}</small>
					</label>
					<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.notes" :disabled="!!creationResult"></textarea></label>
				</div>
				<p v-if="source && !source.modes_of_payment.length" class="form-error" role="alert">{{ __("No configured modes of payment are available for this company.") }}</p>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="busy" @click="close">{{ __("Cancel") }}</button>
				<button class="button" :disabled="busy || !source || !source.modes_of_payment.length">{{ busy ? __("Processing...") : creationResult ? __("Retry Upload") : __("Create and Submit") }}</button>
			</div>
		</form>
	</dialog>
</template>
