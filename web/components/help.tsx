'use client';

// How to use the app. It opens on every visit until the person asks not to show it again, and always from "?".

import { type ReactNode, useEffect, useRef, useState } from 'react';
import { FREE_LEGEND } from '@/lib/format';
import { Close, Help as HelpIcon } from '@/components/icons';
import { ChanceArt, GoalArt, RecommendArt, StartArt } from '@/components/onboarding-art';
import { useMessages } from '@/lib/i18n';

const HIDDEN_KEY = 'ecobici-help-hidden-v1';

function hidden() {
  try {
    return localStorage.getItem(HIDDEN_KEY) === '1';
  } catch {
    return false;
  }
}

function saveHidden(hide: boolean) {
  try {
    if (hide) localStorage.setItem(HIDDEN_KEY, '1');
    else localStorage.removeItem(HIDDEN_KEY);
  } catch {
    // No localStorage (private mode): the modal opens on the next visit.
  }
}

const ARTS: ((props: { label: string }) => ReactNode)[] = [StartArt, GoalArt, RecommendArt, ChanceArt];

export function Help() {
  const t = useMessages();
  const steps = t.help.steps;
  const dialog = useRef<HTMLDialogElement>(null);
  const [dontShow, setDontShow] = useState(false);
  const [step, setStep] = useState(0);
  const open = () => {
    setDontShow(hidden());
    setStep(0);
    dialog.current?.showModal();
  };
  const close = () => dialog.current?.close();
  const last = step === steps.length - 1;
  const Art = ARTS[step];
  const { art, title, text } = steps[step];

  useEffect(() => {
    if (!hidden()) open();
  }, []);

  return (
    <>
      <button type="button" className="icon-btn topbar__help" aria-label={t.help.open} title={t.help.open} onClick={open}>
        <HelpIcon />
      </button>
      <dialog
        ref={dialog}
        className="help"
        aria-labelledby="help-title"
        // Also on Esc, which closes the dialog without a click.
        onClose={() => saveHidden(dontShow)}
        // A click on the backdrop reaches the dialog itself, not its content.
        onClick={(e) => e.target === e.currentTarget && close()}
      >
        <div className="help__body">
          <div className="help__head">
            <span className="help__brand">¡Sí hay!</span>
            <button type="button" className="icon-btn" aria-label={t.help.close} onClick={close}>
              <Close />
            </button>
          </div>
          <div className="help__step" aria-live="polite">
            <Art label={art} />
            <h2 id="help-title">{title}</h2>
            <p>{text}</p>
            {last && (
              <div className="card__legend-items help__legend">
                {FREE_LEGEND.map((l, i) => (
                  <span key={l}>
                    <i className={`swatch swatch--${i}`} aria-hidden="true" /> {l}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="help__dots" role="group" aria-label={t.help.stepsLabel}>
            {steps.map((s, i) => (
              <button
                key={s.title}
                type="button"
                className={`help__dot ${i === step ? 'is-on' : ''}`}
                aria-label={t.help.step(i + 1, s.title)}
                aria-current={i === step ? 'step' : undefined}
                onClick={() => setStep(i)}
              />
            ))}
          </div>
          <div className="help__foot">
            <label className="help__dont-show">
              <input type="checkbox" checked={dontShow} onChange={(e) => setDontShow(e.target.checked)} />
              {t.help.dontShow}
            </label>
            <div className="help__nav">
              {step > 0 && (
                <button type="button" className="help__back" onClick={() => setStep(step - 1)}>
                  {t.help.back}
                </button>
              )}
              <button type="button" className="help__ok" autoFocus onClick={() => (last ? close() : setStep(step + 1))}>
                {last ? t.help.start : t.help.next}
              </button>
            </div>
          </div>
        </div>
      </dialog>
    </>
  );
}
