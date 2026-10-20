// Global prototype augmentations used by the tinySA decode pages
// (implementations live in App.tsx / Spectrum.tsx).
interface Uint8Array {
  indexOfMulti(searchElements: ArrayLike<number>, fromIndex?: number): number;
  endsWith(suffix: ArrayLike<number>): boolean;
}
