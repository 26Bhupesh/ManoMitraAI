import { useTranslation } from "react-i18next";
import { Brain, Languages } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LANGUAGES = [
  { code: "en" as const, label: "English" },
  { code: "hi" as const, label: "हिंदी" },
  { code: "mr" as const, label: "मराठी" },
] as const;

const Header = () => {
  const { t, i18n } = useTranslation();

  const handleLanguageChange = (lng: "en" | "hi" | "mr") => {
    i18n.changeLanguage(lng);
    localStorage.setItem("ui_language", lng);
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-card/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-chat items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <Brain className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="font-heading text-lg font-bold text-foreground leading-tight">
              {t("header_title")}
            </h1>
            <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              aria-label={t("language")}
            >
              <Languages className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {LANGUAGES.map(({ code, label }) => (
              <DropdownMenuItem
                key={code}
                onClick={() => handleLanguageChange(code)}
                className={cn(i18n.language === code && "bg-accent")}
              >
                {label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
};

export default Header;
