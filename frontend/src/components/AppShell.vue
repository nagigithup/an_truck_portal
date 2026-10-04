<script setup>
import { onMounted, onBeforeUnmount, provide, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { boot, call, session } from "../api";
import { __ } from "../i18n";
import Sidebar from "./Sidebar.vue";
import TopHeader from "./TopHeader.vue";
import LoadingState from "./LoadingState.vue";
import EmptyState from "./EmptyState.vue";
import AppButton from "./AppButton.vue";
const route = useRoute(),
	ctx = reactive({ companies: [], company: null, permissions: {}, ready: false }),
	refreshKey = ref(0),
	navOpen = ref(false),
	error = ref(""),
	leaveGuard = ref(null),
	notification = ref("");
provide("portal", { ctx, refreshKey, leaveGuard, notification });
async function initialize() {
	error.value = "";
	try {
		Object.assign(ctx, await call("an_truck_portal.api.context.get_context"));
		ctx.company = ctx.companies.some((c) => c.name === ctx.default_company)
			? ctx.default_company
			: "";
		ctx.ready = true;
	} catch (e) {
		error.value = e.message;
	}
}
async function changeCompany(event) {
	const company = event.target.value;
	event.target.value = ctx.company || "";
	if (leaveGuard.value && !(await leaveGuard.value())) return;
	ctx.company = company;
}
async function refresh() {
	if (!leaveGuard.value || (await leaveGuard.value())) refreshKey.value++;
}
watch(
	() => route.fullPath,
	() => {
		navOpen.value = false;
	},
);
onMounted(() => {
	if (boot.allowed) initialize();
	window.addEventListener("resize", closeDesktopDrawer);
});
function closeDesktopDrawer() {
	if (window.innerWidth > 1000) navOpen.value = false;
}
onBeforeUnmount(() => window.removeEventListener("resize", closeDesktopDrawer));
</script>
<template>
	<main v-if="!boot.allowed" class="center">
		<div class="panel">
			<h1>{{ boot.app_title }}</h1>
			<p>{{ __("You do not have access to this portal.") }}</p>
			<a href="/app">{{ __("Open Desk") }}</a>
		</div>
	</main>
	<div v-else class="shell">
		<a href="#main-content" class="skip-link">{{ __("Skip to content") }}</a
		><Sidebar :ctx="ctx" :open="navOpen" @close="navOpen = false" />
		<div class="main" :inert="navOpen || undefined">
			<TopHeader
				:ctx="ctx"
				:open="navOpen"
				@menu="navOpen = true"
				@company="changeCompany"
				@refresh="refresh"
			/>
			<main id="main-content" tabindex="-1">
				<EmptyState
					v-if="session.ended"
					:message="__('Your session has ended.')"
					error
				/><EmptyState v-else-if="error" :message="__(error)" error
					><AppButton @click="initialize">{{ __("Retry") }}</AppButton></EmptyState
				><LoadingState v-else-if="!ctx.ready" /><template v-else
					><div v-if="notification" class="notice success-notice" role="status">
						{{ __(notification)
						}}<button class="text-button" @click="notification = ''">
							{{ __("Close") }}
						</button>
					</div>
					<router-view :key="`${route.fullPath}-${ctx.company}-${refreshKey}`"
				/></template>
			</main>
		</div>
	</div>
</template>
