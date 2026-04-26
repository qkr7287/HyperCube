<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';

	onMount(() => {
		if (browser) goto(`${base}/`, { replaceState: true });
	});
</script>

<!-- Legacy URL redirect: /admin/dashboard → / -->
