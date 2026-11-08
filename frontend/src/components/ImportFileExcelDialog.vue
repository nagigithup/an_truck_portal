<script setup>
import { inject, ref, watch } from "vue";
import { call, downloadFile, __ } from "../api";
import { language } from "../i18n";
import FormField from "./FormField.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
const emit=defineEmits(["imported"]);
const {ctx}=inject("portal");
const dialog=ref(null),confirm=ref(null),content=ref(""),filename=ref(""),duplicates=ref("skip"),result=ref(null),error=ref(""),busy=ref(false),input=ref(null);
const base="an_truck_portal.api.import_file_excel.";
function open(){content.value="";filename.value="";result.value=null;error.value="";if(input.value)input.value.value="";dialog.value.showModal();}
function close(){if(!busy.value)dialog.value.close();}
async function select(event){
 result.value=null;error.value="";content.value="";
 const file=event.target.files?.[0];if(!file)return;
 if(!file.name.toLowerCase().endsWith('.xlsx')||file.size>2*1024*1024){error.value=__("Select an XLSX file up to 2 MB.");return;}
 filename.value=file.name;
 try{content.value=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});}
 catch{error.value=__("Unable to read the workbook.");}
}
async function template(){busy.value=true;error.value="";try{await downloadFile(base+'template',{company:ctx.company},'import-files-template.xlsx');}catch(e){error.value=e.message;}finally{busy.value=false;}}
async function run(operation){
 if(busy.value||!content.value)return;
 if(operation==='import'&&!(await confirm.value.ask()))return;
 busy.value=true;error.value="";
 try{result.value=await call(base+'import_rows',{company:ctx.company,content:content.value,operation,duplicates:duplicates.value},true);if(result.value.created)emit('imported');}
 catch(e){error.value=e.message;}finally{busy.value=false;}
}
watch([duplicates,language],()=>{result.value=null;});
defineExpose({open});
</script>
<template>
 <dialog ref="dialog" class="operation-dialog wide-dialog import-excel-dialog" :aria-label="__('Import Excel')" @cancel.prevent="close">
  <form @submit.prevent="run('validate')">
   <div class="dialog-head"><h2>{{ __('Import Excel') }}</h2><button type="button" class="icon" :disabled="busy" :aria-label="__('Close')" @click="close">×</button></div>
   <div class="dialog-body">
    <p>{{ __('Import creates new import files only. Vehicle and financial totals are read-only. Existing records are never updated.') }}</p>
    <p>{{ __('All rows must validate before any records are created.') }}</p>
    <div class="form-grid">
     <FormField :model-value="ctx.company || ''" :label="__('Company')" disabled />
     <FormField v-model="duplicates" type="select" :label="__('Duplicate Handling')" :disabled="busy" :options="[{value:'skip',label:'Skip Duplicates'},{value:'error',label:'Reject Duplicates'}]" />
     <label class="form-field"><span>{{ __('Excel File') }}</span><input ref="input" type="file" accept=".xlsx" :disabled="busy" @change="select" /></label>
     <div><button type="button" class="button secondary" :disabled="busy || !ctx.company" @click="template">{{ __('Download Template') }}</button><small>{{ filename }}</small></div>
    </div>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-if="result?.created" class="notice">{{ __('Import completed. Records created: {0}',[result.created]) }}</p>
    <div v-if="result" class="table-wrap"><table><thead><tr><th>{{ __('Row') }}</th><th>{{ __('Name') }}</th><th>{{ __('Status') }}</th><th>{{ __('Message') }}</th></tr></thead><tbody><tr v-for="row in result.rows" :key="row.row"><td>{{ row.row }}</td><td>{{ row.name }}</td><td>{{ __({valid:'Valid',skipped:'Skipped',error:'Error',created:'Created'}[row.status]) }}</td><td>{{ row.message }}</td></tr></tbody></table></div>
   </div>
   <div class="dialog-actions"><button type="button" class="button secondary" :disabled="busy" @click="close">{{ __('Close') }}</button><button type="submit" class="button secondary" :disabled="busy || !content || !ctx.company">{{ __('Validate Rows') }}</button><button type="button" class="button" :disabled="busy || !result?.can_import" @click="run('import')">{{ __('Import Validated Rows') }}</button></div>
  </form>
 </dialog>
 <ConfirmDialog ref="confirm" title="Import Excel" message="Create the validated import files? Existing records will remain unchanged." confirm-label="Import Excel" cancel-label="Cancel" />
</template>
<style scoped>
.import-excel-dialog form{display:flex;flex-direction:column;max-height:90vh;}
.import-excel-dialog .dialog-body{overflow:auto;min-height:0;}
.import-excel-dialog .dialog-head,.import-excel-dialog .dialog-actions{flex-shrink:0;}
.import-excel-dialog .dialog-actions{flex-wrap:wrap;}
.import-excel-dialog small{display:block;margin-top:8px;}
@media(max-width:700px){.import-excel-dialog .form-grid{grid-template-columns:minmax(0,1fr);}}
</style>
