import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";

interface Props {
  question: string;
  onAnswer: (value: number) => void;
  disabled: boolean;
}

const OPTION_KEYS = [
  "screening_option_0",
  "screening_option_1",
  "screening_option_2",
  "screening_option_3",
] as const;

const ScreeningPanel = ({ question, onAnswer, disabled }: Props) => {
  const { t } = useTranslation();
  const options = OPTION_KEYS.map((key, index) => ({
    value: index,
    label: t(key),
  }));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="px-4 pb-2"
    >
      <div className="rounded-2xl border border-border bg-card p-4 shadow-card">
        <p className="mb-4 text-sm font-medium text-foreground">{t(question)}</p>
        <div className="flex flex-col gap-2">
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onAnswer(opt.value)}
              disabled={disabled}
              className="rounded-xl border border-border bg-muted px-4 py-3 text-left text-sm font-medium text-foreground transition-colors hover:border-primary hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                {opt.value}
              </span>
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  );
};

export default ScreeningPanel;
