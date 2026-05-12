declare module '@xterm/xterm' {
	export class Terminal {
		cols: number;
		rows: number;
		constructor(options?: any);
		loadAddon(addon: any): void;
		open(element: HTMLElement): void;
		onData(callback: (data: string) => void): { dispose(): void };
		write(data: string | Uint8Array): void;
		clear(): void;
		dispose(): void;
	}
}

declare module '@xterm/addon-fit' {
	export class FitAddon {
		fit(): void;
		dispose?(): void;
	}
}

declare module '@xterm/xterm/css/xterm.css';
