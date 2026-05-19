/**
 * vitest setup — node 환경 테스트엔 영향 없고, jsdom 환경에서만
 * @testing-library/jest-dom 매처(toBeInTheDocument 등)를 등록.
 */
import '@testing-library/jest-dom/vitest';
