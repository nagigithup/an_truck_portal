<script setup>
import { language, __ } from "../i18n";
import { call } from "../api";
async function toggle() {
 language.value=language.value==='ar'?'en':'ar';
 try {await call('an_truck_portal.api.preferences.set_language',{language:language.value},true);}
 catch { /* Browser preference remains usable offline. */ }
}
</script>
<template><button type="button" class="language-switch" :aria-label="__('Language')" @click="toggle">{{ language==='ar'?'English':'العربية' }}</button></template>
