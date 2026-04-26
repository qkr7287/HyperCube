<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';

	let {
		text,
		placement = 'bottom-start',
	}: {
		text: string;
		placement?: 'top' | 'bottom' | 'left' | 'right' | 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';
	} = $props();
</script>

<InfoTooltip {text} label="Metric help" {placement} />
