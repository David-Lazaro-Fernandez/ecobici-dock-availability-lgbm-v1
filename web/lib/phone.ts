import { useSyncExternalStore } from 'react';

// Same breakpoint as the phone @media block in app/globals.css.
export const PHONE = '(max-width: 700px)';

export const isPhone = () => window.matchMedia(PHONE).matches;

export function usePhone() {
  return useSyncExternalStore(
    (notify) => {
      const q = window.matchMedia(PHONE);
      q.addEventListener('change', notify);
      return () => q.removeEventListener('change', notify);
    },
    isPhone,
    () => false,
  );
}
