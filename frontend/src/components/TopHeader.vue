<script setup>
import { ref, watch, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import IconMenu from "~icons/lucide/menu";
import IconRefresh from "~icons/lucide/refresh-cw";
import IconUser from "~icons/lucide/user-round";
import SearchInput from "./SearchInput.vue";
import { boot, call } from "../api";
import { __, language } from "../i18n";
import { recordLocation } from "../navigation";
const props = defineProps({ ctx: Object, open: Boolean });
const emit = defineEmits(["menu", "company", "refresh"]);
const route = useRoute(),
	q = ref(""),
	results = ref([]),
	searching = ref(false),
	error = ref(""),
	account = ref(null);
let timer,
	generation = 0;
watch([q, () => props.ctx.company], ([value]) => {
	clearTimeout(timer);
	const request = ++generation;
	results.value = [];
	error.value = "";
	searching.value = value.trim().length > 1;
	if (!searching.value) return;
	timer = setTimeout(async () => {
		try {
			const rows = await call("an_truck_portal.api.search.search", {
				q: value,
				company: props.ctx.company,
			});
			if (request === generation) results.value = rows;
		} catch (e) {
			if (request === generation) error.value = e.message;
		} finally {
			if (request === generation) searching.value = false;
		}
	}, 250);
});
watch(
	() => route.fullPath,
	() => {
		q.value = "";
		if (account.value) account.value.open = false;
	},
);
onBeforeUnmount(() => {
	clearTimeout(timer);
	generation++;
});
</script>
<template>
	<header class="top-header">
		<button
			class="icon mobile"
			:aria-label="__('Open menu')"
			aria-controls="portal-sidebar"
			:aria-expanded="open"
			@click="emit('menu')"
		>
			<IconMenu />
		</button>
		<SearchInput v-model="q" :placeholder="__('search.placeholder')" @keydown.esc="q = ''"
			><div v-if="q.trim().length > 1" class="search-results" aria-live="polite">
				<p v-if="searching">{{ __("Searching…") }}</p>
				<p v-else-if="error" class="error">{{ __(error) }}</p>
				<template v-else
					><template v-for="result in results" :key="`${result.doctype}-${result.name}`"
						><router-link
							v-if="recordLocation(result).to"
							:to="recordLocation(result).to"
							@click="q = ''"
							>{{ result.label
							}}<small
								>{{ __(result.doctype) }} · <bdi>{{ result.name }}</bdi></small
							></router-link
						><a v-else :href="recordLocation(result).href"
							>{{ result.label
							}}<small
								>{{ __(result.doctype) }} · <bdi>{{ result.name }}</bdi></small
							></a
						></template
					>
					<p v-if="!results.length">{{ __("No results") }}</p></template
				>
			</div></SearchInput
		>
		<div class="header-controls">
			<label v-if="ctx.companies.length" class="company-picker"
				><span class="sr-only">{{ __("Company context") }}</span
				><select :value="ctx.company || ''" @change="emit('company', $event)">
					<option value="">{{ __("All companies") }}</option>
					<option
						v-for="company in ctx.companies"
						:key="company.name"
						:value="company.name"
					>
						{{ company.name }}
					</option>
				</select></label
			>
			<button
				class="language-switch"
				:aria-label="__('Language')"
				@click="language = language === 'ar' ? 'en' : 'ar'"
			>
				<span lang="ar">العربية</span><span aria-hidden="true"> / </span
				><span lang="en">EN</span>
			</button>
			<button
				class="icon"
				:title="__('Refresh')"
				:aria-label="__('Refresh')"
				@click="emit('refresh')"
			>
				<IconRefresh />
			</button>
			<details ref="account" class="account" @keydown.esc="account.open = false">
				<summary :aria-label="__('Account')">
					<IconUser /><span>{{ boot.full_name }}</span>
				</summary>
				<div class="account-menu">
					<b>{{ boot.full_name }}</b
					><a href="/app">{{ __("Open Desk") }}</a
					><a href="/?cmd=web_logout">{{ __("Sign out") }}</a>
				</div>
			</details>
		</div>
	</header>
</template>
