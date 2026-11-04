<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { call, __ } from "../api";
import FormField from "./FormField.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import LanguageSwitch from "./LanguageSwitch.vue";
const emit = defineEmits(["saved"]);
const base = "an_truck_portal.api.vouchers.";
const dialog = ref(null), confirmation = ref(null), options = ref(null), form = ref({}), busy = ref(false), error = ref(""), calculation = ref(null), invoices = ref([]), partyCurrency = ref("");
const title = computed(() => form.value.name ? form.value.payment_type === "Receive" ? "Edit Receipt Voucher" : "Edit Payment Voucher" : form.value.payment_type === "Receive" ? "Create Receipt Voucher" : "Create Payment Voucher");
const isReceipt = computed(() => form.value.payment_type === "Receive");
const account = computed(() => options.value?.accounts.find(row => row.name === form.value.account));
const accounts = computed(() => {
 const mode = options.value?.modes.find(row => row.name === form.value.mode_of_payment);
 return (options.value?.accounts || []).filter(row => !mode || mode.type === "General" || row.account_type === mode.type);
});
let timer, generation = 0;
async function open(direction = "Receive", name = "") {
 error.value = ""; calculation.value = null; invoices.value = []; options.value = null;
 form.value = {}; dialog.value.showModal(); busy.value = true;
 try {
  options.value = await call(base + "get_options");
  let doc = null;
  if (name) doc = (await call(base + "get_voucher", { name })).document;
  form.value = doc ? {...doc, account: doc.payment_type === "Receive" ? doc.paid_to : doc.paid_from,
    amount: doc.payment_type === "Receive" ? doc.received_amount : doc.paid_amount,
    references: (await call(base + "get_voucher", { name })).references} : {
    company: options.value.company, payment_type: direction, posting_date: options.value.today,
    party_type: direction === "Receive" ? "Customer" : "Supplier", party: "", mode_of_payment: "", account: "", amount: "", reference_no: "", reference_date: "", remarks: "", references: [],
    request_key: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`};
  if (doc) await loadInvoices(false);
 } catch(e) { error.value = e.message; } finally { busy.value = false; }
}
function close() { if (!busy.value) { generation++; clearTimeout(timer); dialog.value.close(); } }
function partyTypeChanged() { form.value.party = ""; form.value.references = []; invoices.value = []; }
async function loadInvoices(reset = true) {
 if (!form.value.party) return;
 const selectedParty=form.value.party, selectedType=form.value.party_type;
 const previous = reset ? [] : (invoices.value.length ? invoices.value : form.value.references || []);
 if (reset) { form.value.references = []; invoices.value = []; }
 try {
  const data = await call(base + "get_outstanding", { party_type: form.value.party_type, party: form.value.party, direction: form.value.payment_type, date: form.value.posting_date });
  if(form.value.party!==selectedParty || form.value.party_type!==selectedType)return;
  partyCurrency.value = data.currency;
  const existing = previous;
  invoices.value = data.rows.map(row => ({...row, reference_doctype: row.voucher_type, reference_name: row.voucher_no,
   allocated_amount: existing.find(old => old.reference_doctype === row.voucher_type && old.reference_name === row.voucher_no && (old.payment_term || "") === (row.payment_term || ""))?.allocated_amount || 0}));
  for (const row of existing) if (!invoices.value.some(current => current.reference_doctype === row.reference_doctype && current.reference_name === row.reference_name && (current.payment_term || "") === (row.payment_term || ""))) invoices.value.push({...row,voucher_type:row.reference_doctype,voucher_no:row.reference_name});
 } catch(e) { error.value = e.message; }
}
function modeChanged() {
 const mode = options.value.modes.find(row => row.name === form.value.mode_of_payment);
 form.value.account = mode?.default_account || "";
 if (mode?.requires_reference && !form.value.reference_date) form.value.reference_date = form.value.posting_date;
}
function data() { return {...form.value, references: invoices.value.filter(row => Number(row.allocated_amount)).map(row => ({reference_doctype:row.reference_doctype,reference_name:row.reference_name,payment_term:row.payment_term,allocated_amount:row.allocated_amount}))}; }
watch(() => [form.value.party, form.value.party_type, form.value.account, form.value.mode_of_payment, form.value.posting_date, form.value.amount], () => {
 clearTimeout(timer); calculation.value = null;
 const request = ++generation;
 if (!form.value.party || !form.value.account || !form.value.mode_of_payment || !(Number(form.value.amount)>0)) return;
 timer = setTimeout(async () => {
  try { const result = await call(base + "preview", {data:data(), name:form.value.name}, true); if (request === generation) {calculation.value = result;error.value='';} }
  catch(e) { if (request === generation) error.value = e.message; }
 }, 400);
});
async function save(submit = false) {
 if (busy.value || !options.value) return;
 if (!dialog.value.querySelector('form').reportValidity()) return;
 if (submit && !(await confirmation.value.ask())) return;
 busy.value = true; error.value = ""; generation++; clearTimeout(timer);
 try {
  if(form.value.name) {const current=await call(base+'get_voucher',{name:form.value.name});if(current.document.docstatus===1){dialog.value.close();emit('saved',form.value.name);return;}}
  let result = await call(base + "save_voucher", {data:data(),name:form.value.name,modified:form.value.modified,request_key:form.value.request_key}, true);
  Object.assign(form.value, {name:result.document.name,modified:result.document.modified});
  if (submit) result = await call(base + "action", {name:form.value.name,action:"submit",modified:form.value.modified}, true);
  dialog.value.close(); emit("saved",result.document.name);
 } catch(e) { error.value = e.message; } finally { busy.value = false; }
}
onBeforeUnmount(() => { clearTimeout(timer); generation++; });
defineExpose({open});
</script>
<template>
 <dialog ref="dialog" class="operation-dialog wide-dialog voucher-form" :aria-label="__(title)" @cancel.prevent="close">
  <form @submit.prevent="save(false)" @invalid.capture.prevent="error = __('Complete the required voucher fields.')">
   <div class="dialog-head"><h2>{{ __(title) }}</h2><div class="page-actions"><LanguageSwitch /><button type="button" class="icon" :disabled="busy" :aria-label="__('Close')" @click="close">×</button></div></div>
   <div class="dialog-body">
    <p v-if="!options">{{ __('Loading…') }}</p>
    <div v-else class="form-grid">
     <FormField :model-value="form.company" :label="__('Company')" disabled />
     <FormField v-model="form.posting_date" type="date" :label="__('Posting Date')" required :disabled="busy" />
     <FormField v-model="form.party_type" type="select" :options="options.party_types" :label="__('Party Type')" required :disabled="busy || !!form.name" @update:model-value="partyTypeChanged" />
     <div><FormField v-model="form.party" :label="__(isReceipt ? 'Received From' : 'Pay To')" :link="{method:base+'party_options',party_type:form.party_type}" required :disabled="busy" @change="loadInvoices" /><small v-if="calculation?.party_name">{{ calculation.party_name }}</small></div>
     <FormField v-model.number="form.amount" type="number" min="0" step="any" :label="__('Amount')" required :disabled="busy" />
     <FormField :model-value="account?.account_currency || ''" :label="__('Currency')" disabled />
     <FormField v-model="form.mode_of_payment" type="select" :options="options.modes.map(row=>row.name)" :label="__('Payment Method')" required :disabled="busy" @update:model-value="modeChanged" />
     <FormField v-model="form.account" type="select" :options="accounts.map(row=>row.name)" :label="__(isReceipt ? 'Receiving Account' : 'Paying Account')" required :disabled="busy" />
     <FormField v-model="form.reference_no" :label="__('Reference Number')" :required="account?.account_type === 'Bank'" :disabled="busy" />
     <FormField v-model="form.reference_date" type="date" :label="__('Reference Date')" :required="account?.account_type === 'Bank'" :disabled="busy" />
     <FormField v-model="form.remarks" type="textarea" :label="__('Description')" :disabled="busy" class="field-span-full" />
    </div>
    <div v-if="calculation" class="compact-details"><div><small>{{ __('Paid Amount') }}</small><b>{{ calculation.paid_amount }} {{ calculation.paid_from_account_currency }}</b></div><div><small>{{ __('Received Amount') }}</small><b>{{ calculation.received_amount }} {{ calculation.paid_to_account_currency }}</b></div><div><small>{{ __('Source Exchange Rate') }}</small><b>{{ calculation.source_exchange_rate }}</b></div><div><small>{{ __('Target Exchange Rate') }}</small><b>{{ calculation.target_exchange_rate }}</b></div></div>
    <div class="dialog-section-head"><h3>{{ __('Related Invoices') }} <bdi>{{ partyCurrency }}</bdi></h3><button type="button" class="button secondary small" :disabled="busy || !form.party" @click="loadInvoices(false)">{{ __('Refresh') }}</button></div>
    <div v-if="invoices.length" class="table-wrap"><table><thead><tr><th>{{ __('Invoice') }}</th><th>{{ __('Outstanding Amount') }}</th><th>{{ __('Allocated Amount') }}</th></tr></thead><tbody><tr v-for="(row,index) in invoices" :key="`${row.voucher_type}-${row.voucher_no}-${row.payment_term}`"><td><bdi>{{ row.voucher_no }}</bdi><small>{{ row.payment_term }}</small></td><td>{{ row.outstanding_amount }}</td><td><input v-model.number="row.allocated_amount" type="number" step="any" :min="Math.min(0, row.payment_term_outstanding ?? row.outstanding_amount)" :max="Math.max(0,row.payment_term_outstanding ?? row.outstanding_amount)" :aria-label="`${__('Allocated Amount')} ${index+1}`" :disabled="busy || !['Sales Invoice','Purchase Invoice'].includes(row.reference_doctype)" /></td></tr></tbody></table></div>
    <p v-else class="empty compact">{{ __('No outstanding invoices. The voucher may be saved as an unallocated payment.') }}</p>
    <p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
   </div>
   <div class="dialog-actions"><button type="button" class="button secondary" :disabled="busy" @click="close">{{ __('Cancel') }}</button><button type="submit" class="button secondary" :disabled="busy || !options">{{ __('Save Draft') }}</button><button v-if="options?.can_submit" type="button" class="button" :disabled="busy" @click="save(true)">{{ __('Save and Submit') }}</button></div>
  </form>
 </dialog>
 <ConfirmDialog ref="confirmation" title="Submit Voucher" message="Submit this voucher and post its accounting entries?" confirm-label="Submit" cancel-label="Cancel" />
</template>
<style scoped>
.voucher-form .form-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
.voucher-form .dialog-body {overflow:auto;min-height:0;}
.voucher-form form {max-height:90vh;display:flex;flex-direction:column;}
.voucher-form .dialog-head,.voucher-form .dialog-actions {flex-shrink:0;}
@media(max-width:700px){.voucher-form .form-grid {grid-template-columns:minmax(0,1fr);}}
</style>
