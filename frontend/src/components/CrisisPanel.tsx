import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import type { CrisisResponse } from "@/lib/types";
import { AlertTriangle, Phone } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  data: CrisisResponse;
  onContinue: () => void;
}

const CrisisPanel = ({ data, onContinue }: Props) => {
  const { t } = useTranslation();
  const isHigh = data.crisis_level === "high";

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/30 backdrop-blur-sm p-4"
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3 }}
          className={cn(
            "relative w-full max-w-md rounded-2xl border-2 bg-card p-6 shadow-card",
            isHigh ? "border-crisis-high" : "border-crisis-moderate"
          )}
        >
          <div className="mb-4 flex items-center gap-3">
            <div
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-full",
                isHigh ? "bg-crisis-high/10" : "bg-crisis-moderate/10"
              )}
            >
              <AlertTriangle
                className={cn(
                  "h-5 w-5",
                  isHigh ? "text-crisis-high" : "text-crisis-moderate"
                )}
              />
            </div>
            <h2 className="font-heading text-lg font-bold text-foreground">
              {isHigh ? t("crisis_heading_high") : t("crisis_heading_moderate")}
            </h2>
          </div>

          <p className="mb-3 text-sm leading-relaxed text-foreground">
            {t(`crisis_reason_${data.reason}`)}
          </p>
          {/* <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
            {data.action}
          </p> */}

          <div className="mb-5 rounded-xl bg-muted p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {t("helpline_numbers")}
            </p>
            <div className="flex flex-col gap-1.5 text-sm text-foreground">
              <span className="flex items-center gap-2">
                <Phone className="h-3.5 w-3.5 text-primary" />
                iCall: 9152987821
              </span>
              <span className="flex items-center gap-2">
                <Phone className="h-3.5 w-3.5 text-primary" />
                Vandrevala Foundation: 1860-2662-345
              </span>
              <span className="flex items-center gap-2">
                <Phone className="h-3.5 w-3.5 text-primary" />
                NIMHANS: 080-46110007
              </span>
            </div>
          </div>

          {isHigh && (
            <p className="mb-4 text-sm font-medium text-foreground">
              💛 {t("crisis_trust_message")}
            </p>
          )}

          <button
            onClick={onContinue}
            className={cn(
              "w-full rounded-xl py-3 text-sm font-semibold transition-colors",
              isHigh
                ? "bg-crisis-high text-primary-foreground hover:bg-crisis-high/90"
                : "bg-crisis-moderate text-primary-foreground hover:bg-crisis-moderate/90"
            )}
          >
            {t("continue_chat")}
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default CrisisPanel;
