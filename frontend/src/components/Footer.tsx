import { useTranslation } from "react-i18next";

const Footer = () => {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-border bg-card/60 py-2 text-center">
      <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
        {t("footer_tagline")}
      </p>
    </footer>
  );
};

export default Footer;
