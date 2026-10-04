import { ref, watch } from "vue";
import ar from "./locales/ar.json";
import en from "./locales/en.json";

let saved;
try {
	saved = localStorage.getItem("an-truck-language");
} catch {}
export const language = ref(
	["ar", "en"].includes(saved)
		? saved
		: window.anTruckBoot?.lang?.startsWith("ar")
			? "ar"
			: "en",
);
export function __(key, values = []) {
	let text =
		(language.value === "ar" ? ar[key] : en[key]) ||
		(language.value === "ar" ? window.anTruckBoot?.messages?.[key] : null) ||
		key;
	values.forEach((value, index) => {
		text = text.split(`{${index}}`).join(value);
	});
	return text;
}
watch(
	language,
	(value) => {
		document.documentElement.lang = value;
		document.documentElement.dir = value === "ar" ? "rtl" : "ltr";
		try {
			localStorage.setItem("an-truck-language", value);
		} catch {}
	},
	{ immediate: true },
);
window.__ = __;
