'use client';

import { useEffect } from 'react';
import { GbFlag, MxFlag } from '@/components/flags';
import { type Lang, LANGS, MESSAGES, setLang, useLang } from '@/lib/i18n';

const FLAGS: Record<Lang, () => React.JSX.Element> = { es: MxFlag, en: GbFlag };

export function LangSwitch() {
  const lang = useLang();

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  return (
    <div className="lang" role="radiogroup" aria-label={MESSAGES[lang].langSwitch}>
      {LANGS.map((l) => {
        const Flag = FLAGS[l];
        return (
          <button
            key={l}
            type="button"
            role="radio"
            aria-checked={lang === l}
            lang={l}
            title={MESSAGES[l].langName}
            className={`lang__btn ${lang === l ? 'is-on' : ''}`}
            onClick={() => setLang(l)}
          >
            <Flag />
            <span className="lang__code" aria-hidden="true">{l.toUpperCase()}</span>
            <span className="sr-only">{MESSAGES[l].langName}</span>
          </button>
        );
      })}
    </div>
  );
}
