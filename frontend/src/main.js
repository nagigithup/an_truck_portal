import {createApp} from 'vue';import App from './App.vue';import {router} from './router';import './theme.css';

const boot = window.anTruckBoot || {};

async function removeLegacyPortalCaches() {
	if ('serviceWorker' in navigator) {
		const registrations = await navigator.serviceWorker.getRegistrations();
		await Promise.all(registrations.filter((registration) => {
			const scope = new URL(registration.scope).pathname;
			const script = registration.active?.scriptURL || registration.waiting?.scriptURL || registration.installing?.scriptURL || '';
			return scope.startsWith('/an-truck-portal') || script.includes('an_truck_portal');
		}).map((registration) => registration.unregister()));
	}
	if ('caches' in window) {
		const keys = await caches.keys();
		await Promise.all(keys.filter((key) => key.startsWith('an-truck-portal')).map((key) => caches.delete(key)));
	}
}

let checkingVersion = false;
async function checkForPortalUpdate() {
	if (checkingVersion || !boot.asset_version || document.visibilityState === 'hidden') return;
	checkingVersion = true;
	try {
		const response = await fetch('/api/method/an_truck_portal.api.context.get_asset_version', {
			credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'},
		});
		if (!response.ok) return;
		const latest = String((await response.json()).message || '');
		if (!latest || latest === String(boot.asset_version)) return;
		const notificationKey = `an-truck-portal-update:${latest}`;
		if (sessionStorage.getItem(notificationKey)) return;
		sessionStorage.setItem(notificationKey, 'shown');
		const arabic = String(boot.lang || '').startsWith('ar');
		const message = arabic
			? 'يتوفر تحديث جديد للبوابة. هل تريد إعادة التحميل الآن؟'
			: 'A new portal update is available. Reload now?';
		if (window.confirm(message)) {
			const url = new URL(window.location.href);
			url.searchParams.set('_portal_version', latest);
			window.location.replace(url);
		}
	} catch (error) {
		console.debug('Portal update check failed', error);
	} finally {
		checkingVersion = false;
	}
}

removeLegacyPortalCaches().catch(() => {});
window.addEventListener('focus', checkForPortalUpdate);
document.addEventListener('visibilitychange', checkForPortalUpdate);
setTimeout(checkForPortalUpdate, 60_000);

createApp(App).use(router).mount('#an-truck-portal');
