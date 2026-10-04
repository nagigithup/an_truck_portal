<script setup>
import { __ } from "../i18n";
defineProps({ disabled: [Boolean, Number] });
</script>
<template>
	<span :class="['badge', disabled ? 'neutral' : 'success']">{{
		__(disabled ? "Disabled" : "Active")
	}}</span>
</template>
