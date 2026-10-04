import { onBeforeUnmount, ref } from "vue";
import { call } from "../api";

// One in-flight request and one snapshot per mounted form. Reopening the form
// creates a new instance, so new ERPNext master records are picked up naturally.
export function useFormOptions(method, args) {
	const data = ref({}),
		loading = ref(false),
		error = ref("");
	let pending,
		loaded = false,
		active = true;
	onBeforeUnmount(() => {
		active = false;
	});
	function load() {
		if (pending) return pending;
		if (loaded) return Promise.resolve();
		loading.value = true;
		error.value = "";
		pending = call(method, args())
			.then((result) => {
				if (active) {
					data.value = result;
					loaded = true;
				}
			})
			.catch(() => {
				if (active) error.value = "Unable to load reference data. Please try again.";
			})
			.finally(() => {
				if (active) loading.value = false;
				pending = null;
			});
		return pending;
	}
	return { data, loading, error, load };
}
