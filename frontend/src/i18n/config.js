import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import hi from "./hi.json";
import mr from "./mr.json";

const resources = {
  en: { translation: en },
  hi: { translation: hi },
  mr: { translation: mr }
};

const savedLanguage = localStorage.getItem("ui_language") || "en";

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: savedLanguage,
    fallbackLng: "en",
    supportedLngs: ["en", "hi", "mr"],
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
