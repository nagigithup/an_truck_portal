<script setup>
import { computed } from "vue";
import { __, language } from "../i18n";
const props = defineProps({ name: String, permissions: Object, busy: Boolean });
defineEmits(["edit", "print", "action"]);
const pdf = computed(() => `/api/method/an_truck_portal.api.vouchers.download_pdf?${new URLSearchParams({name: props.name, language: language.value})}`);
</script>
<template>
 <div class="page-actions voucher-actions">
  <button v-if="permissions?.can_edit" type="button" class="button secondary small" :disabled="busy" @click="$emit('edit')">{{ __('Edit Draft') }}</button>
  <button v-if="permissions?.can_print" type="button" class="button secondary small" :disabled="busy" @click="$emit('print')">{{ __('Print') }}</button>
  <a v-if="permissions?.can_print" class="button secondary small" :href="pdf" target="_blank" rel="noopener">{{ __('Download PDF') }}</a>
  <button v-if="permissions?.can_submit" type="button" class="button small" :disabled="busy" @click="$emit('action','submit')">{{ __('Submit') }}</button>
  <button v-if="permissions?.can_cancel" type="button" class="button secondary small" :disabled="busy" @click="$emit('action','cancel')">{{ __('Cancel Voucher') }}</button>
  <button v-for="action in permissions?.workflow_actions || []" :key="action.action" type="button" class="button small" :disabled="busy" @click="$emit('action',action.action)">{{ action.label }}</button>
 </div>
</template>
