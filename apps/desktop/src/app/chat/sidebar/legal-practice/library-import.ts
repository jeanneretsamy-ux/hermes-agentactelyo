export interface PrivateLibraryEntry {
  title: string
  act_type: string
  body: string
  domain: string
}

export function parsePrivateLibrary(text: string, domains: string[]): PrivateLibraryEntry[] {
  if (text.length > 8_000_000) {
    throw new Error('Bibliothèque trop volumineuse (8 Mo maximum).')
  }
  const value = JSON.parse(text)

  if (
    value?.format !== 'actelyo-private-library-v1' ||
    !Array.isArray(value.entries) ||
    value.entries.length < 1 ||
    value.entries.length > 500
  ) {
    throw new Error('Format de bibliothèque Actelyo invalide (1 à 500 actes).')
  }

  const string = (input: unknown, max: number): string => {
    if (typeof input !== 'string' || !input.trim() || input.length > max) {
      throw new Error('Une entrée contient un champ vide, invalide ou trop long.')
    }

    return input
  }

  return value.entries.map((entry: Record<string, unknown>) => {
    if (!entry || !domains.includes(String(entry.domain))) {
      throw new Error('Domaine de bibliothèque inconnu.')
    }
    const title = string(entry.title, 500)
    const source = Array.isArray(entry.sources) ? entry.sources[0] : undefined

    if (!source || typeof source.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(source.sha256)) {
      throw new Error('Provenance SHA-256 manquante.')
    }

    const header = [
      'RÉFÉRENCE PRIVÉE À ADAPTER — NON ANONYMISÉE, NON VALIDÉE',
      'Ce document peut contenir des faits déjà remplis : ne pas les reprendre pour un autre dossier.',
      'Conserver les balises non résolues et demander les données manquantes. Vérifier le droit applicable.',
      `Source : ${string(source.archive, 500)} / ${string(source.member, 1000)}`,
      `SHA-256 original : ${source.sha256}`,
      '--- TEXTE DE RÉFÉRENCE ---'
    ].join('\n')

    const body = header + '\n\n' + string(entry.body, 190_000)

    return { title, act_type: string(entry.act_type, 100), domain: String(entry.domain), body }
  })
}
