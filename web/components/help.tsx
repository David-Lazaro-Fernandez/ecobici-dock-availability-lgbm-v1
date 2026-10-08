'use client';

// How to use the app. It opens on every visit until the person asks not to show it again, and always from "?".

import { type ReactNode, useEffect, useRef, useState } from 'react';
import { FREE_LEGEND } from '@/lib/format';
import { Close, Help as HelpIcon } from '@/components/icons';
import { ChanceArt, GoalArt, RecommendArt, StartArt } from '@/components/onboarding-art';

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

const STEPS: { art: () => ReactNode; title: string; text: ReactNode }[] = [
  {
    art: StartArt,
    title: 'Elige desde dónde sales',
    text: (
      <>
        Escribe una calle, un lugar o una estación, o toca <em>Mi ubicación</em>.
      </>
    ),
  },
  {
    art: GoalArt,
    title: 'Elige a dónde vas',
    text: 'Escríbelo o haz doble clic en el mapa.',
  },
  {
    art: RecommendArt,
    title: 'Sigue la recomendación',
    text: (
      <>
        Te decimos dónde tomar la bici y en qué estación dejarla. La <strong>#1</strong> es la mejor; toca otra para ver su
        ruta.
      </>
    ),
  },
  {
    art: ChanceArt,
    title: 'Qué significa el porcentaje',
    text: (
      <>
        La probabilidad de encontrar lugar libre <strong>a la hora en que llegas</strong>.
      </>
    ),
  },
];

export function Help() {
  const dialog = useRef<HTMLDialogElement>(null);
  const [dontShow, setDontShow] = useState(false);
  const [step, setStep] = useState(0);
  const open = () => {
    setDontShow(hidden());
    setStep(0);
    dialog.current?.showModal();
  };
  const close = () => dialog.current?.close();
  const last = step === STEPS.length - 1;
  const { art: Art, title, text } = STEPS[step];

  useEffect(() => {
    if (!hidden()) open();
  }, []);

  return (
    <>
      <button type="button" className="icon-btn topbar__help" aria-label="Cómo usar la app" title="Cómo usar la app" onClick={open}>
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
            <button type="button" className="icon-btn" aria-label="Cerrar" onClick={close}>
              <Close />
            </button>
          </div>
          <div className="help__step" aria-live="polite">
            <Art />
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
          <div className="help__dots" role="group" aria-label="Pasos">
            {STEPS.map((s, i) => (
              <button
                key={s.title}
                type="button"
                className={`help__dot ${i === step ? 'is-on' : ''}`}
                aria-label={`Paso ${i + 1}: ${s.title}`}
                aria-current={i === step ? 'step' : undefined}
                onClick={() => setStep(i)}
              />
            ))}
          </div>
          <div className="help__foot">
            <label className="help__dont-show">
              <input type="checkbox" checked={dontShow} onChange={(e) => setDontShow(e.target.checked)} />
              No volver a mostrar
            </label>
            <div className="help__nav">
              {step > 0 && (
                <button type="button" className="help__back" onClick={() => setStep(step - 1)}>
                  Atrás
                </button>
              )}
              <button type="button" className="help__ok" autoFocus onClick={() => (last ? close() : setStep(step + 1))}>
                {last ? 'Empezar' : 'Siguiente'}
              </button>
            </div>
          </div>
        </div>
      </dialog>
    </>
  );
}
