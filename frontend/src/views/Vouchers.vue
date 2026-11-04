<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { call, __ } from "../api";
import { language } from "../i18n";
import VoucherFormDialog from "../components/VoucherFormDialog.vue";
import VoucherActions from "../components/VoucherActions.vue";
import DocumentPrintDialog from "../components/DocumentPrintDialog.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
const props = defineProps({name: {default:""}, direction:{default:""}});
const router = useRouter(), base="an_truck_portal.api.vouchers.";
const result=ref(null), error=ref(""), loading=ref(false), busy=ref(false), search=ref(""), status=ref(""), page=ref(1), fromDate=ref(""), toDate=ref("");
const formDialog=ref(null), printDialog=ref(null), confirm=ref(null), printName=ref(""), pendingAction=ref("");
const pendingTitle=ref("");
const title=computed(()=>props.direction==="Receive"?"Receipt Vouchers":props.direction==="Pay"?"Payment Vouchers":"All Vouchers");
const doc=computed(()=>result.value?.document || {});
const metrics=[['total','Total Vouchers'],['receipts','Receipt Vouchers'],['payments','Payment Vouchers'],['draft','Draft Vouchers'],['submitted','Submitted Vouchers'],['cancelled','Cancelled Vouchers']];
let timer, generation=0;
function type(value){return value==='Receive'?'Receipt Voucher':value==='Pay'?'Payment Voucher':'Transfer Voucher';}
function money(value,currency){try{return new Intl.NumberFormat(language.value,{style:'currency',currency:currency||'SAR'}).format(Number(value||0));}catch{return `${value} ${currency||''}`;}}
function amount(row){return money(row.payment_type==='Receive'?row.received_amount:row.paid_amount,row.payment_type==='Receive'?row.paid_to_account_currency:row.paid_from_account_currency);}
function date(value){return value?new Intl.DateTimeFormat(language.value,{dateStyle:'medium'}).format(new Date(value+'T12:00:00')):'—';}
function state(row){return row.actions?.workflow_state || (props.name && result.value?.workflow_state) || __(({0:'Draft',1:'Submitted',2:'Cancelled'})[row.docstatus]);}
async function load(){
 const request=++generation; loading.value=true;error.value='';
 try {const data=await call(base+(props.name?'get_voucher':'list_vouchers'),props.name?{name:props.name}:{direction:props.direction,search:search.value,status:status.value,from_date:fromDate.value,to_date:toDate.value,page:page.value});if(request===generation)result.value=data;}
 catch(e){if(request===generation)error.value=e.message;}finally{if(request===generation)loading.value=false;}
}
async function saved(name){if(props.name===name)await load();else await router.push('/vouchers/'+encodeURIComponent(name));}
async function print(name){printName.value=name;await nextTick();printDialog.value.open();}
async function perform(row,action){
 if(busy.value)return;
 busy.value=true;error.value='';
 pendingAction.value=action;
 try {const current=await call(base+'get_voucher',{name:row.name});pendingTitle.value=current.workflow_actions?.find(row=>row.action===action)?.label||action;if(!(await confirm.value.ask()))return;await call(base+'action',{name:row.name,action,modified:current.document.modified},true);await load();}
 catch(e){error.value=e.message;}finally{busy.value=false;}
}
watch([search,status,fromDate,toDate],()=>{page.value=1;clearTimeout(timer);timer=setTimeout(load,300);});
watch([()=>props.name,()=>props.direction],()=>{page.value=1;result.value=null;load();});
onMounted(load);onBeforeUnmount(()=>{clearTimeout(timer);generation++;});
</script>
<template>
 <div class="page financial-vouchers">
  <header class="page-head"><div><p class="eyebrow">{{ __('Financial Vouchers') }}</p><h1>{{ name?doc.name:__(title) }}</h1><small v-if="result">{{ name?doc.company:result.company }}</small></div><div v-if="!name && result?.can_create" class="page-actions"><button v-if="direction!=='Pay'" class="button" @click="formDialog.open('Receive')">{{ __('Create Receipt Voucher') }}</button><button v-if="direction!=='Receive'" class="button" @click="formDialog.open('Pay')">{{ __('Create Payment Voucher') }}</button></div><router-link v-if="name" class="button secondary" to="/vouchers">{{ __('All Vouchers') }}</router-link></header>
  <p v-if="error" class="notice error-notice" role="alert">{{ __(error) }}</p>
  <template v-if="!name">
   <div v-if="result?.counts" class="voucher-metrics"><div v-for="[key,label] in metrics" :key="key" class="panel"><small>{{ __(label) }}</small><strong>{{ result.counts[key] }}</strong></div></div>
   <div class="panel form-grid voucher-filters"><label><span>{{ __('Search') }}</span><input v-model="search" :placeholder="__('Voucher number, party or reference')" /></label><label><span>{{ __('Status') }}</span><select v-model="status"><option value="">{{ __('All statuses') }}</option><option value="0">{{ __('Draft') }}</option><option value="1">{{ __('Submitted') }}</option><option value="2">{{ __('Cancelled') }}</option></select></label><label><span>{{ __('From Date') }}</span><input v-model="fromDate" type="date" /></label><label><span>{{ __('To Date') }}</span><input v-model="toDate" type="date" /></label></div>
   <p v-if="loading" class="empty">{{ __('Loading…') }}</p>
   <div v-else-if="result" class="panel table-wrap"><table><thead><tr><th>{{ __('Voucher Number') }}</th><th>{{ __('Voucher Type') }}</th><th>{{ __('Date') }}</th><th>{{ __('Customer / Supplier') }}</th><th>{{ __('Amount') }}</th><th>{{ __('Currency') }}</th><th>{{ __('Payment Method') }}</th><th>{{ __('Status') }}</th><th>{{ __('Actions') }}</th></tr></thead><tbody><tr v-if="!result.rows.length"><td colspan="9" class="empty">{{ __('No vouchers found.') }}</td></tr><tr v-for="row in result.rows" :key="row.name"><td><router-link :to="'/vouchers/'+encodeURIComponent(row.name)"><bdi>{{ row.name }}</bdi></router-link></td><td>{{ __(type(row.payment_type)) }}</td><td>{{ date(row.posting_date) }}</td><td>{{ row.party_name||row.party||'—' }}</td><td><bdi>{{ amount(row) }}</bdi></td><td>{{ row.payment_type==='Receive'?row.paid_to_account_currency:row.paid_from_account_currency }}</td><td>{{ __(row.mode_of_payment||'') }}</td><td><span class="badge neutral">{{ state(row) }}</span></td><td><router-link class="text-button" :to="'/vouchers/'+encodeURIComponent(row.name)">{{ __('View') }}</router-link><VoucherActions :name="row.name" :permissions="row.actions" :busy="busy" @edit="formDialog.open(row.payment_type,row.name)" @print="print(row.name)" @action="perform(row,$event)" /></td></tr></tbody></table></div>
   <div class="pagination"><button class="button secondary" :disabled="loading||page<=1" @click="page--;load()">{{ __('Previous') }}</button><span>{{ __('Page') }} {{ page }}</span><button class="button secondary" :disabled="loading||!result?.has_more" @click="page++;load()">{{ __('Next') }}</button></div>
  </template>
  <template v-else-if="result?.document">
   <section class="panel section-card"><div class="section-head"><h2>{{ __(type(doc.payment_type)) }}</h2><span class="badge neutral">{{ state(doc) }}</span></div><VoucherActions :name="doc.name" :permissions="result" :busy="busy" @edit="formDialog.open(doc.payment_type,doc.name)" @print="print(doc.name)" @action="perform(doc,$event)" /><div class="compact-details"><div v-for="[key,label] in [['party_name','Party'],['party_type','Party Type'],['posting_date','Posting Date'],['mode_of_payment','Payment Method'],['paid_from','Paid From'],['paid_to','Paid To'],['reference_no','Reference Number'],['reference_date','Reference Date']]" :key="key"><small>{{ __(label) }}</small><b>{{ key==='mode_of_payment'||key==='party_type'?__(doc[key]||''):doc[key]||'—' }}</b></div><div><small>{{ __('Paid Amount') }}</small><bdi>{{ money(doc.paid_amount,doc.paid_from_account_currency) }}</bdi></div><div><small>{{ __('Received Amount') }}</small><bdi>{{ money(doc.received_amount,doc.paid_to_account_currency) }}</bdi></div><div><small>{{ __('Source Exchange Rate') }}</small><bdi>{{ doc.source_exchange_rate }}</bdi></div><div><small>{{ __('Target Exchange Rate') }}</small><bdi>{{ doc.target_exchange_rate }}</bdi></div><div><small>{{ __('Unallocated Amount') }}</small><bdi>{{ doc.unallocated_amount }}</bdi></div></div><p class="detail-notes">{{ doc.remarks }}</p></section>
   <section class="panel section-card"><h2>{{ __('Related Invoices') }}</h2><div class="table-wrap"><table><thead><tr><th>{{ __('Invoice') }}</th><th>{{ __('Outstanding Amount') }}</th><th>{{ __('Allocated Amount') }}</th></tr></thead><tbody><tr v-for="row in result.references" :key="row.reference_name+'-'+row.payment_term"><td><bdi>{{ row.reference_name }}</bdi><small>{{ row.payment_term }}</small></td><td>{{ row.outstanding_amount }}</td><td>{{ row.allocated_amount }}</td></tr><tr v-if="!result.references.length"><td colspan="3" class="empty">{{ __('No linked invoices.') }}</td></tr></tbody></table></div></section>
  </template>
  <VoucherFormDialog ref="formDialog" @saved="saved" />
  <DocumentPrintDialog ref="printDialog" doctype="Payment Entry" :document-name="printName" />
  <ConfirmDialog ref="confirm" :title="pendingAction==='cancel'?'Cancel Voucher':pendingAction==='submit'?'Submit Voucher':pendingTitle" :message="pendingAction==='cancel'?'Cancel this voucher and reverse its accounting entries?':pendingAction==='submit'?'Submit this voucher and post its accounting entries?':'Apply this workflow action?'" confirm-label="Confirm" cancel-label="Cancel" />
 </div>
</template>
<style scoped>
.voucher-metrics {display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:16px;}
.voucher-metrics .panel {padding:16px;display:flex;flex-direction:column;gap:8px;}
.voucher-metrics strong {font-size:1.6rem;}
.voucher-filters {padding:16px;margin-bottom:16px;}
.financial-vouchers :deep(.voucher-actions) {gap:5px;flex-wrap:wrap;}
@media(max-width:980px){.voucher-metrics{grid-template-columns:repeat(3,minmax(0,1fr));}}
@media(max-width:600px){.voucher-metrics{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
