/**
 * Keyboard + external reset triggers. Mouse-wheel zoom is delegated
 * to OrbitControls entirely — this controller never fires focus
 * events from the wheel (req #11).
 */
export class InputController {
	private keyHandler: ((e: KeyboardEvent) => void) | null = null;

	attach(onReset: () => void): void {
		this.detach();
		const handler = (e: KeyboardEvent) => {
			if (e.key === 'Escape') onReset();
		};
		window.addEventListener('keydown', handler);
		this.keyHandler = handler;
	}

	detach(): void {
		if (this.keyHandler) {
			window.removeEventListener('keydown', this.keyHandler);
			this.keyHandler = null;
		}
	}
}
