/**
 * Per-page hero content that the user layout's top bar renders.
 *
 * /user 페이지가 onMount 시 set(...), onDestroy 시 set(null) 하면
 * 레이아웃이 자동으로 header 안에 title / KPI / action 버튼을 그린다.
 *
 * KPI / action 은 markup 이 아니라 plain data (label / value / onclick) 라
 * 레이아웃이 일관된 visual 로 렌더 — 페이지마다 디자인이 갈리지 않게 강제.
 */
import { writable } from 'svelte/store';

export type UserHeaderKpi = {
	key: string;
	label: string;
	value: string;
	tone?: 'container' | 'request' | 'gpu' | 'ws';
	on?: boolean;
	title?: string;
};

export type UserHeaderAction = {
	label: string;
	onclick: () => void;
	variant?: 'ghost' | 'primary' | 'icon';
	disabled?: boolean;
	spinning?: boolean;
};

export type UserHeaderPayload = {
	title?: string;
	subtitle?: string;
	kpis?: UserHeaderKpi[];
	actions?: UserHeaderAction[];
};

export const userHeaderStore = writable<UserHeaderPayload | null>(null);
