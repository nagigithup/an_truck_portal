<script setup>
import { __ } from "../i18n";
</script>
<template>
	<div class="empty" role="status" aria-live="polite">
		<span class="spinner" />{{ __("Loading") }}
	</div>
</template>
