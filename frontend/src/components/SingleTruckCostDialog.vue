<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import FormField from "./FormField.vue";
import { call, __ } from "../api";
const props=defineProps({importFile:String,accounts:Array});
const emit=defineEmits(["created"]);
const dialog=ref(null),form=ref({}),target=ref(null),review=ref(null),error=ref(""),busy=ref(false),finding=ref(false);
const requestKey=ref(""),attempted=ref(false);
const base="an_truck_portal.api.import_file.";
const currency=computed(()=>props.accounts?.find(a=>a.name===form.value.expense_account)?.account_currency || target.value?.company_currency || "");
let generation=0,timer;
onBeforeUnmount(()=>{clearTimeout(timer);generation++;});
function open(){
 clearTimeout(timer);generation++;target.value=null;review.value=null;error.value="";attempted.value=false;finding.value=false;
 form.value={vehicle:"",amount:"",expense_account:"",description:""};
 requestKey.value=globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
 dialog.value.showModal();
}
function close(){if(!busy.value){clearTimeout(timer);generation++;dialog.value.close();}}
watch(()=>form.value.vehicle,vehicle=>{
 clearTimeout(timer);const current=++generation;target.value=null;review.value=null;finding.value=!!vehicle;
 if(!vehicle)return;
 timer=setTimeout(async()=>{
  try{const result=await call(base+'get_single_truck_cost_target',{vehicle_import_file:props.importFile,vehicle});if(current===generation){target.value=result;error.value="";}}
  catch(e){if(current===generation)error.value=e.message;}
  finally{if(current===generation)finding.value=false;}
 },300);
});
watch(form,()=>{if(!attempted.value)review.value=null;},{deep:true});
async function preview(){
 if(busy.value)return;
 busy.value=true;error.value="";
 try{review.value=await call(base+'preview_single_truck_cost',{vehicle_import_file:props.importFile,data:form.value},true);}
 catch(e){error.value=e.message;}finally{busy.value=false;}
}
async function submit(){
 if(busy.value||!review.value)return;
 busy.value=true;error.value="";attempted.value=true;
 try{
  const result=await call(base+'create_single_truck_cost',{vehicle_import_file:props.importFile,data:form.value,
   request_key:requestKey.value,confirmation:review.value.confirmation},true);
  dialog.value.close();emit('created',result);
 }catch(e){
  error.value=e.message;
  if(e.message===__('Cost details changed. Review the confirmation again.')){attempted.value=false;review.value=null;}
 }finally{busy.value=false;}
}
function edit(){if(!attempted.value)review.value=null;}
defineExpose({open});
</script>
<template>
 <dialog ref="dialog" class="operation-dialog wide-dialog single-truck-cost-dialog" :aria-label="__('Add Cost to One Truck')" @cancel.prevent="close">
  <form @submit.prevent="review ? submit() : preview()">
   <div class="dialog-head"><h2>{{ __('Add Cost to One Truck') }}</h2><button type="button" class="icon" :disabled="busy" :aria-label="__('Close')" @click="close">×</button></div>
   <div class="dialog-body">
    <p>{{ __('The entire additional cost will be assigned to this VIN only.') }}</p>
    <div v-if="!review" class="form-grid">
     <FormField v-model="form.vehicle" :label="__('VIN / Chassis Number')" required ltr :disabled="busy || attempted" :link="{method:base+'search_single_truck_cost_vehicles',vehicle_import_file:importFile}" />
     <FormField v-model="form.amount" type="number" min="0" step="any" :label="__('Cost Amount')" required :disabled="busy || attempted" />
     <FormField v-model="form.expense_account" type="select" :label="__('Expense Account')" required :disabled="busy || attempted" :options="(accounts || []).map(a=>({value:a.name,label:a.name}))" />
     <FormField :model-value="currency" :label="__('Currency')" disabled ltr />
     <FormField v-model="form.description" type="textarea" :label="__('Description')" :disabled="busy || attempted" />
    </div>
    <p v-if="finding">{{ __('Loading...') }}</p>
    <p v-if="target && !target.eligible" class="form-error" role="alert">{{ __(target.reason) }}</p>
    <div v-if="review || target" class="target-summary">
     <h3>{{ __(review ? 'Confirm Single-Truck Cost' : 'Target Vehicle') }}</h3>
     <p v-if="(review?.summary || target).doctype === 'Stock Reconciliation'">{{ __('Stock Reconciliation revalues this on-hand VIN without changing the net stock quantity.') }}</p>
     <dl>
      <dt>{{ __('Document Type') }}</dt><dd>{{ __((review?.summary || target).doctype) }}</dd>
      <dt>{{ __('VIN / Chassis Number') }}</dt><dd><bdi>{{ (review?.summary || target).vin }}</bdi></dd>
      <dt>{{ __('Vehicle Import File') }}</dt><dd><bdi>{{ importFile }}</bdi></dd>
      <dt>{{ __('Target Vehicle') }}</dt><dd><bdi>{{ (review?.summary || target).vehicle }} · {{ (review?.summary || target).item_name }}</bdi></dd>
      <dt>{{ __('Company') }}</dt><dd>{{ (review?.summary || target).company }}</dd>
      <dt>{{ __('Warehouse') }}</dt><dd>{{ (review?.summary || target).warehouse }}</dd>
      <dt>{{ __('Purchase Receipt') }}</dt><dd><bdi>{{ (review?.summary || target).purchase_receipt }}</bdi></dd>
      <dt>{{ __('Receipt Currency') }}</dt><dd><bdi>{{ (review?.summary || target).receipt_currency }}</bdi></dd>
      <template v-if="review">
       <template v-if="review.summary.doctype === 'Stock Reconciliation'">
        <dt>{{ __('Current Serial Valuation') }}</dt><dd><bdi>{{ review.summary.current_valuation }} {{ review.summary.company_currency }}</bdi></dd>
        <dt>{{ __('New Serial Valuation') }}</dt><dd><bdi>{{ review.summary.new_valuation }} {{ review.summary.company_currency }}</bdi></dd>
       </template>
       <dt>{{ __('Cost Amount') }}</dt><dd><bdi>{{ review.summary.amount }} {{ review.summary.currency }}</bdi></dd>
       <dt>{{ __('Amount (Company Currency)') }}</dt><dd><bdi>{{ review.summary.company_amount }} {{ review.summary.company_currency }}</bdi></dd>
       <dt>{{ __('Exchange Rate') }}</dt><dd><bdi>{{ review.summary.exchange_rate }}</bdi></dd>
       <dt>{{ __('Expense Account') }}</dt><dd>{{ review.summary.expense_account }}</dd>
       <dt>{{ __('Description') }}</dt><dd>{{ review.summary.description || '—' }}</dd>
      </template>
     </dl>
    </div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-if="attempted && error">{{ __('Retry this same request to retrieve its voucher without creating a duplicate.') }}</p>
   </div>
   <div class="dialog-actions">
    <button type="button" class="button secondary" :disabled="busy" @click="close">{{ __('Cancel') }}</button>
    <button v-if="review && !attempted" type="button" class="button secondary" :disabled="busy" @click="edit">{{ __('Edit') }}</button>
    <button type="submit" class="button" :disabled="busy || finding || !review && !target?.eligible">{{ __(busy ? 'Processing...' : review ? 'Confirm and Submit' : 'Review Cost') }}</button>
   </div>
  </form>
 </dialog>
</template>
<style scoped>
.single-truck-cost-dialog form{display:flex;flex-direction:column;max-height:90vh;}
.single-truck-cost-dialog .dialog-body{overflow:auto;min-height:0;}
.single-truck-cost-dialog .dialog-head,.single-truck-cost-dialog .dialog-actions{flex-shrink:0;}
.single-truck-cost-dialog .dialog-actions{flex-wrap:wrap;}
.target-summary{margin-block:20px;}
.target-summary dl{display:grid;grid-template-columns:minmax(120px,1fr) minmax(0,2fr);gap:10px;}
.target-summary dd{margin:0;overflow-wrap:anywhere;}
@media(max-width:700px){.single-truck-cost-dialog .form-grid{grid-template-columns:minmax(0,1fr);}.target-summary dl{grid-template-columns:1fr;gap:5px;}.target-summary dd{margin-block-end:8px;}}
</style>
