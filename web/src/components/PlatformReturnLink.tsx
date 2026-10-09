import { ArrowLeft } from "lucide-react";

interface PlatformReturnLinkProps {
  compact?: boolean;
}

export function PlatformReturnLink({
  compact = false,
}: PlatformReturnLinkProps) {
  return (
    <a
      href="https://actelyo.com/dashboard"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Retour à la plateforme Actelyo (nouvel onglet)"
      title="Retour à la plateforme Actelyo — nouvel onglet"
      className={`flex shrink-0 items-center gap-2 rounded-md text-sm text-text-secondary hover:text-midground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-midground ${compact ? "justify-center p-2" : "mx-3 my-2 px-2 py-2"}`}
    >
      <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden="true" />
      {!compact && <span>Retour à la plateforme</span>}
    </a>
  );
}
