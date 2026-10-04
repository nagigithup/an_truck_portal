<script setup>
import { __ } from "../i18n";
</script>
<template>
	<div class="filter-bar" role="search" :aria-label="__('Filters')"><slot /></div>
</template>
