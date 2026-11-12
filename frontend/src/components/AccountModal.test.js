import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// The navbar has a backdrop blur, which makes it the containing block for `position: fixed` children.
// A modal rendered inside it is squashed into the 64px header (it was cut off at the top on screen).
// So the account window must be portalled to <body>. Verified visually in a real browser on 2026-11-12.
describe('AccountModal placement', () => {
  it('is rendered into document.body, not inside the navbar', () => {
    const source = readFileSync(new URL('./AccountModal.jsx', import.meta.url), 'utf8');
    expect(source).toMatch(/createPortal\(/);
    expect(source).toMatch(/document\.body/);
  });
});
