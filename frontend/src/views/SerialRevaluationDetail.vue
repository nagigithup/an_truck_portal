<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
const props=defineProps({name:String});
const doc=ref(null),error=ref('');
const status=computed(()=>doc.value?.docstatus===1?'Submitted':doc.value?.docstatus===2?'Cancelled':'Draft');
async function load(){doc.value=null;error.value='';try{doc.value=await call('an_truck_portal.api.import_file.get_single_truck_revaluation',{name:props.name});}catch(e){error.value=e.message;}}
onMounted(load);watch(()=>props.name,load);
const fields={vin:'VIN / Chassis Number',vehicle:'Target Vehicle',company:'Company',warehouse:'Warehouse',posting_date:'Posting Date',
 expense_account:'Expense Account',requested_amount:'Requested Additional Cost',amount:'Posted Valuation Change',previous_valuation:'Current Serial Valuation',
 new_valuation:'New Serial Valuation',quantity:'Quantity',currency:'Currency',description:'Description'};
</script>
<template>
 <div class="page">
  <p v-if="error" class="panel empty error" role="alert">{{ error }}</p>
  <div v-else-if="!doc" class="panel empty">{{ __('Loading...') }}</div>
  <template v-else>
   <header class="page-head"><div><p class="eyebrow">{{ __('Stock Reconciliation') }}</p><h1><bdi>{{ doc.name }}</bdi></h1></div><span class="badge">{{ __(status) }}</span></header>
   <div class="page-actions">
    <router-link :to="{name:'import-workspace',params:{name:doc.vehicle_import_file}}">{{ __('Vehicle Import File') }}: {{ doc.vehicle_import_file }}</router-link>
    <router-link :to="{name:'purchase-receipt-detail',params:{name:doc.purchase_receipt}}">{{ __('Original Purchase Receipt') }}: {{ doc.purchase_receipt }}</router-link>
    <a class="button secondary small" :href="`/app/stock-reconciliation/${encodeURIComponent(doc.name)}`" target="_blank" rel="noopener">{{ __('Open in Desk') }}</a>
   </div>
   <section class="panel section-card"><h2>{{ __('Serial Valuation Adjustment') }}</h2><div class="form-grid">
    <div v-for="(label,key) in fields" :key="key" class="form-field"><small>{{ __(label) }}</small><b><bdi>{{ doc[key] ?? '—' }}</bdi></b></div>
   </div></section>
  </template>
 </div>
</template>
