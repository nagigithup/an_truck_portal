<script setup>
import { computed, ref, watch, nextTick } from "vue";
import IconHome from "~icons/lucide/layout-dashboard";
import IconShip from "~icons/lucide/ship";
import IconTruck from "~icons/lucide/truck";
import IconShopping from "~icons/lucide/shopping-cart";
import IconUsers from "~icons/lucide/users";
import IconClose from "~icons/lucide/x";
import { navigation } from "../navigation";
import { __ } from "../i18n";
const props = defineProps({ open: Boolean, ctx: Object });
const emit = defineEmits(["close"]);
const sidebar = ref(null),
	closeButton = ref(null);
const icons = [IconHome, IconShip, IconShopping, IconTruck, IconUsers];
const groups = computed(() =>
	navigation
		.map((group, i) => ({
			...group,
			icon: icons[i],
			items: group.items.filter((item) => !item[2] || props.ctx.permissions[item[2]]?.read),
		}))
		.filter((group) => group.items.length),
);
let previousFocus;
watch(
	() => props.open,
	async (open) => {
		if (open) {
			previousFocus = document.activeElement;
			await nextTick();
			closeButton.value?.focus();
		} else previousFocus?.focus();
	},
);
function trap(event) {
	if (!props.open || event.key !== "Tab") return;
	const elements = [...sidebar.value.querySelectorAll("a, button")].filter(
		(el) => el.offsetParent !== null,
	);
	const first = elements[0],
		last = elements.at(-1);
	if (event.shiftKey && document.activeElement === first) {
		event.preventDefault();
		last.focus();
	} else if (!event.shiftKey && document.activeElement === last) {
		event.preventDefault();
		first.focus();
	}
}
</script>
<template>
	<aside
		id="portal-sidebar"
		ref="sidebar"
		:class="['sidebar', { open }]"
		:aria-label="__('Main navigation')"
		@keydown.esc="emit('close')"
		@keydown="trap"
	>
		<div class="brand">
			<img src="/assets/an_truck_portal/logo.svg" alt="" />
			<div>
				<b>AN TRUCK</b><small>{{ ctx.company || __("Operations") }}</small>
			</div>
			<button
				ref="closeButton"
				class="icon mobile sidebar-close"
				:aria-label="__('Close menu')"
				@click="emit('close')"
			>
				<IconClose />
			</button>
		</div>
		<nav :aria-label="__('Main navigation')">
			<div v-for="group in groups" :key="group.label" class="nav-group">
				<p class="nav-label">{{ __(group.label) }}</p>
				<router-link
					v-for="item in group.items"
					:key="item[0]"
					:to="item[0]"
					:class="{
						'nav-active':
							item[0] === '/'
								? $route.path === '/'
								: $route.path === item[0] || $route.path.startsWith(`${item[0]}/`),
					}"
					><component :is="group.icon" aria-hidden="true" /><span>{{
						__(item[1])
					}}</span></router-link
				>
			</div>
		</nav>
		<footer>
			<a href="/app">{{ __("Open Desk") }}</a
			><a href="/?cmd=web_logout">{{ __("Sign out") }}</a>
		</footer>
	</aside>
	<button
		v-if="open"
		class="overlay"
		tabindex="-1"
		:aria-label="__('Close menu')"
		@click="emit('close')"
	/>
</template>
