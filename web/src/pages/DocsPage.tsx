import { useLayoutEffect } from "react";
import { ExternalLink } from "lucide-react";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

export const HERMES_DOCS_URL = "https://github.com/jeanneretsamy-ux/hermes-agentactelyo/blob/main/ACTELYO-LOCAL.md";

export default function DocsPage() {
  const { t } = useI18n();
  const { setEnd } = usePageHeader();
  useLayoutEffect(() => {
    setEnd(<a href={HERMES_DOCS_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-midground">
      <ExternalLink className="size-3.5" />{t.app.openDocumentation}
    </a>);
    return () => setEnd(null);
  }, [setEnd, t]);
  return <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 p-4 text-midground">
    <PluginSlot name="docs:top" />
    <h1 className="text-2xl font-bold">Actelyo Law Harness</h1>
    <p>Module agent local complémentaire à Actelyo. Son compte et ses autorisations sont distincts de ceux de l’ERP.</p>
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Installation locale</h2>
      <p>Extrayez le kit de modules locaux téléchargé depuis les paramètres Actelyo, puis exécutez ces commandes dans ce dossier :</p>
      <pre className="overflow-x-auto p-3"><code>{"python actelyo-local.py prepare harness\npython actelyo-local.py up harness\npython actelyo-local.py status"}</code></pre>
      <p>Interface : http://127.0.0.1:9119. Utilisateur : actelyo. Le mot de passe est ACTELYO_HARNESS_PASSWORD dans le fichier .env du kit.</p>
    </section>
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Configurer un modèle</h2>
      <p>Configurez votre fournisseur dans le module. Pour Legal Inference dans le même réseau Compose, utilisez http://legal-inference:8080/v1 et l’identifiant exact du modèle chargé.</p>
      <p>Aucun modèle juridique entraîné n’est inclus. Les services externes optionnels conservent leurs propres comptes et conditions.</p>
    </section>
    <a href={HERMES_DOCS_URL} target="_blank" rel="noopener noreferrer" className="underline">Guide de déploiement Actelyo</a>
    <PluginSlot name="docs:bottom" />
  </div>;
}
