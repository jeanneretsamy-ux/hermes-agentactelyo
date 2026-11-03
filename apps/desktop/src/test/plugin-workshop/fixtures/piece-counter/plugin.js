import React from 'react'

function CompteurPieces() {
  const [count, setCount] = React.useState(0)
  const buttonStyle = {
    padding: '0.5rem 0.75rem',
    border: '1px solid var(--ui-border, currentColor)',
    borderRadius: '0.375rem',
    color: 'inherit',
    background: 'var(--ui-bg, transparent)',
    cursor: 'pointer'
  }

  return React.createElement('section', {
    'aria-label': 'Compteur de pièces',
    style: { padding: '1rem', color: 'var(--ui-text-primary, inherit)' }
  },
  React.createElement('h2', { style: { margin: '0 0 0.75rem' } }, 'Compteur de pièces'),
  React.createElement('output', {
    'aria-label': 'Nombre de pièces',
    'aria-live': 'polite',
    'aria-atomic': true,
    style: { display: 'block', fontSize: '2rem', marginBottom: '1rem', fontVariantNumeric: 'tabular-nums' }
  }, String(count)),
  React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem' } },
    React.createElement('button', {
      type: 'button', style: buttonStyle,
      onClick: () => setCount(value => Math.min(Number.MAX_SAFE_INTEGER, value + 1))
    }, 'Ajouter'),
    React.createElement('button', {
      type: 'button', style: { ...buttonStyle, opacity: count === 0 ? 0.5 : 1 },
      disabled: count === 0,
      onClick: () => setCount(value => Math.max(0, value - 1))
    }, 'Retirer'),
    React.createElement('button', {
      type: 'button', style: buttonStyle,
      onClick: () => setCount(0)
    }, 'Remettre à zéro')
  ))
}

const HermesPlugin = {
  id: 'actelyo-compteur-pieces',
  name: 'Compteur de pièces',
  description: 'Ajouter, retirer et remettre à zéro un nombre de pièces, sans valeur négative. État limité au panneau ouvert.',
  defaultEnabled: false,
  register(ctx) {
    ctx.register({
      id: 'panel',
      area: 'secondarySidebar',
      title: 'Compteur de pièces',
      render: () => React.createElement(CompteurPieces)
    })
  }
}

export default HermesPlugin
