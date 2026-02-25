import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Brain, Languages, LogOut } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getAuthState, logout as logoutSession, getSessionId } from "@/lib/session";
import { logout as apiLogout } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const LANGUAGES = [
  { code: "en" as const, label: "English" },
  { code: "hi" as const, label: "हिंदी" },
  { code: "mr" as const, label: "मराठी" },
] as const;

const Header = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { toast } = useToast();
  const authState = getAuthState();

  const handleLanguageChange = (lng: "en" | "hi" | "mr") => {
    // Only change UI language for this session, do not persist
    i18n.changeLanguage(lng);
  };

  const handleLogout = async () => {
    try {
      const sessionId = getSessionId();
      await apiLogout(sessionId);
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      logoutSession();
      toast({
        title: t("success"),
        description: t("logout_successful"),
      });
      navigate("/login");
    }
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

        <div className="flex items-center gap-2">
          {authState && (
            <div className="text-right mr-2 hidden sm:block">
              <p className="text-sm font-medium text-foreground">{authState.username}</p>
              <p className="text-xs text-muted-foreground">{t("logged_in")}</p>
            </div>
          )}

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

          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            className="shrink-0"
            aria-label={t("logout")}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
};

export default Header;
