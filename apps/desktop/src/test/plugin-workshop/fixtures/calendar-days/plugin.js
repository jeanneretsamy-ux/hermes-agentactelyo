import React from 'react';

const h = React.createElement;

function calculate(dateText, daysText) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateText)) throw new Error('Saisissez une date de départ valide.');
  const [year, month, day] = dateText.split('-').map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(0, 0, 0, 0);
  if (year < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new Error('Saisissez une date de départ valide.');
  }
  if (!/^\d+$/.test(daysText)) throw new Error('Saisissez un nombre entier de jours positif ou nul.');
  const days = Number(daysText);
  if (!Number.isSafeInteger(days) || days > 3652058) throw new Error('Nombre de jours trop élevé.');
  date.setUTCDate(date.getUTCDate() + days);
  if (!Number.isFinite(date.getTime()) || date.getUTCFullYear() > 9999) throw new Error('La date obtenue dépasse le 31/12/9999.');
  return date.toISOString().slice(0, 10);
}

function CalendarDaysPanel() {
  const [date, setDate] = React.useState('');
  const [days, setDays] = React.useState('');
  const [result, setResult] = React.useState('');
  const [error, setError] = React.useState('');
  const prefix = React.useId();
  function update(setter, value) {
    setter(value);
    setResult('');
    setError('');
  }
  function submit(event) {
    event.preventDefault();
    try { setResult(calculate(date, days)); setError(''); }
    catch (err) { setResult(''); setError(err.message); }
  }
  function clear() {
    setDate(''); setDays(''); setResult(''); setError('');
  }
  const fieldStyle = { display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 6, padding: 8, color: 'inherit', background: 'var(--background, transparent)', border: '1px solid var(--border, #888)', borderRadius: 6 };
  return h('section', { 'aria-label': 'Calcul de jours calendaires', style: { padding: 16, color: 'var(--foreground, inherit)' } },
    h('h2', null, 'Date après N jours'),
    h('p', { id: prefix + '-help' }, 'Ajoute des jours calendaires à la date de départ. Le jour de départ est le jour zéro ; week-ends et jours fériés sont inclus.'),
    h('form', { onSubmit: submit, noValidate: true, 'aria-describedby': prefix + '-help', style: { display: 'grid', gap: 14 } },
      h('label', { htmlFor: prefix + '-date' }, 'Date de départ',
        h('input', { id: prefix + '-date', type: 'date', min: '0001-01-01', max: '9999-12-31', value: date, onChange: event => update(setDate, event.target.value), style: fieldStyle })),
      h('label', { htmlFor: prefix + '-days' }, 'Nombre de jours calendaires',
        h('input', { id: prefix + '-days', type: 'number', min: '0', step: '1', inputMode: 'numeric', value: days, onChange: event => update(setDays, event.target.value), style: fieldStyle })),
      h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
        h('button', { type: 'submit' }, 'Calculer'),
        h('button', { type: 'button', onClick: clear }, 'Effacer')),
      error ? h('p', { role: 'alert' }, error) : null,
      h('output', { 'aria-live': 'polite', 'aria-label': 'Date obtenue' }, result ? 'Date obtenue : ' + result.split('-').reverse().join('/') : '')),
    h('p', { style: { fontSize: '0.85em', opacity: 0.8 } }, 'Addition de dates uniquement : aucune règle de délai procédural appliquée.'));
}

const HermesPlugin = {
  id: 'actelyo-calendar-days',
  name: 'Jours calendaires',
  description: 'Calculer une date après un nombre de jours calendaires et effacer les saisies.',
  defaultEnabled: false,
  register(ctx) {
    ctx.register({ id: 'calendar-days-panel', area: 'secondarySidebar', title: 'Jours calendaires', render: () => h(CalendarDaysPanel) });
  }
};

export default HermesPlugin;
