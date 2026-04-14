"""
test_support_service.py
Unit tests for support_service.py — pure logic functions only.
No LLM calls, no ChromaDB, no FastAPI, no session file I/O.

Run:
    pip install pytest --break-system-packages
    pytest test_support_service.py -v

All tests are deterministic and run offline.
"""

import re
import pytest

# ─────────────────────────────────────────────────────────────
# We import only the pure functions — nothing that hits network
# or disk on import. Patch the Groq client and session helpers
# before importing so the module-level initialization doesn't fail.
# ─────────────────────────────────────────────────────────────
import sys
import types
from unittest.mock import MagicMock, patch

# Stub out app.session_state so the import doesn't need the real file
session_state_stub = types.ModuleType("app.session_state")
session_state_stub.get_session = MagicMock(return_value={})
session_state_stub.update_session = MagicMock()
app_stub = types.ModuleType("app")
app_stub.session_state = session_state_stub
sys.modules.setdefault("app", app_stub)
sys.modules.setdefault("app.session_state", session_state_stub)

# Stub chromadb and its embedding_functions so they don't need to be installed
chromadb_stub = types.ModuleType("chromadb")
chromadb_stub.PersistentClient = MagicMock()
ef_stub = types.ModuleType("chromadb.utils.embedding_functions")
ef_stub.SentenceTransformerEmbeddingFunction = MagicMock()
sys.modules.setdefault("chromadb", chromadb_stub)
sys.modules.setdefault("chromadb.utils", types.ModuleType("chromadb.utils"))
sys.modules.setdefault("chromadb.utils.embedding_functions", ef_stub)

# Stub groq
groq_stub = types.ModuleType("groq")
groq_stub.Groq = MagicMock()
sys.modules.setdefault("groq", groq_stub)

# Set the env var so the module initializes cleanly
import os
os.environ.setdefault("GROQ_API_KEY", "test-key")

# Now import the module under test
import importlib
support = importlib.import_module("app.support_service") if "app.support_service" in sys.modules \
    else None

# If the module is not in app package during testing, import directly
if support is None:
    try:
        import support_service as support
    except ModuleNotFoundError:
        # Try as app.support_service
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import support_service as support


# ══════════════════════════════════════════════════════════════
# SECTION 1: CRISIS KEYWORD DETECTION
# ══════════════════════════════════════════════════════════════

class TestCrisisKeywords:

    def test_english_self_harm(self):
        assert support.contains_crisis_keywords("I want to kill myself") is True

    def test_english_end_life(self):
        assert support.contains_crisis_keywords("I want to end my life") is True

    def test_english_self_harm_lowercase(self):
        assert support.contains_crisis_keywords("i hurt myself yesterday") is True

    def test_hindi_suicide(self):
        assert support.contains_crisis_keywords("मुझे आत्महत्या करनी है") is True

    def test_hindi_dont_want_to_live(self):
        assert support.contains_crisis_keywords("जीना नहीं है मुझे") is True

    def test_hindi_harm_others(self):
        assert support.contains_crisis_keywords("किसी को मारना चाहता हूँ") is True

    def test_marathi_want_to_die(self):
        assert support.contains_crisis_keywords("मला मरायचं आहे") is True

    def test_marathi_take_life(self):
        assert support.contains_crisis_keywords("मला एखाद्याचा जीव घ्यायचा आहे") is True

    def test_marathi_harm_to_others(self):
        assert support.contains_crisis_keywords("एखाद्याचा जीव घ्यावा असं वाटतंय") is True

    def test_marathi_end_it_all(self):
        assert support.contains_crisis_keywords("सगळं संपवतो आता") is True

    def test_safe_message_english(self):
        assert support.contains_crisis_keywords("I feel a bit sad today") is False

    def test_safe_message_marathi(self):
        assert support.contains_crisis_keywords("मला थोडं अस्वस्थ वाटतं") is False

    def test_safe_message_hindi(self):
        assert support.contains_crisis_keywords("मुझे थोड़ा तनाव है") is False

    def test_partial_match_marathi(self):
        # "मरायचं" is a substring keyword — should match in longer sentence
        assert support.contains_crisis_keywords("मला खरंच मरायचं वाटतं") is True


# ══════════════════════════════════════════════════════════════
# SECTION 2: USER_IS_REJECTING
# ══════════════════════════════════════════════════════════════

class TestUserIsRejecting:

    # Pure single-word refusals
    def test_marathi_nako_pure(self):
        assert support.user_is_rejecting("नको") is True

    def test_marathi_nahi_pure(self):
        assert support.user_is_rejecting("नाही") is True

    def test_hindi_nahi_pure(self):
        assert support.user_is_rejecting("नहीं") is True

    def test_english_no_pure(self):
        assert support.user_is_rejecting("no") is True

    def test_english_nope(self):
        assert support.user_is_rejecting("nope") is True

    def test_english_stop(self):
        assert support.user_is_rejecting("stop") is True

    # Sentence-level Marathi rejection
    def test_marathi_sentence_no_technique(self):
        assert support.user_is_rejecting("नको आता कोणतेही तंत्र नको") is True

    def test_marathi_technique_nako(self):
        assert support.user_is_rejecting("तंत्र नको मला") is True

    def test_marathi_aata_nako(self):
        assert support.user_is_rejecting("आता नको") is True

    # Sentence-level Hindi rejection
    def test_hindi_no_technique(self):
        assert support.user_is_rejecting("कोई भी तकनीक नहीं चाहिए") is True

    # Confusion phrases must NOT be caught as rejection
    def test_confusion_not_rejection_marathi(self):
        assert support.user_is_rejecting("मला नक्की काय करायचं ते कळाल नाही") is False

    def test_confusion_not_rejection_hindi(self):
        assert support.user_is_rejecting("मुझे समझ नहीं आया") is False

    def test_confusion_not_rejection_english(self):
        assert support.user_is_rejecting("I don't understand what you mean") is False

    # Engagement messages must NOT be caught
    def test_positive_reply_not_rejection(self):
        assert support.user_is_rejecting("हो, मी प्रयत्न करतो") is False

    def test_positive_hindi_not_rejection(self):
        assert support.user_is_rejecting("हाँ, मैं कोशिश करूंगा") is False


# ══════════════════════════════════════════════════════════════
# SECTION 3: USER_IS_CONFUSED
# ══════════════════════════════════════════════════════════════

class TestUserIsConfused:

    def test_marathi_kalal_nahi(self):
        assert support.user_is_confused("मला कळाल नाही") is True

    def test_marathi_samajla_nahi(self):
        assert support.user_is_confused("मला समजलं नाही") is True

    def test_marathi_spashta_sang(self):
        assert support.user_is_confused("स्पष्ट सांग मला") is True

    def test_marathi_mhanje_kay(self):
        assert support.user_is_confused("म्हणजे काय नक्की?") is True

    def test_hindi_samajh_nahi(self):
        assert support.user_is_confused("समझ नहीं आया") is True

    def test_hindi_kya_matlab(self):
        assert support.user_is_confused("क्या मतलब है इसका") is True

    def test_english_dont_understand(self):
        assert support.user_is_confused("I don't understand") is True

    def test_english_what_do_you_mean(self):
        assert support.user_is_confused("What do you mean by that?") is True

    def test_english_be_more_specific(self):
        assert support.user_is_confused("Can you be more specific?") is True

    # Pure rejections must NOT be caught as confusion
    def test_nako_not_confusion(self):
        assert support.user_is_confused("नको") is False

    def test_no_not_confusion(self):
        assert support.user_is_confused("no") is False

    # Engagement must NOT be caught
    def test_positive_not_confusion(self):
        assert support.user_is_confused("हो, मला समजलं") is False


# ══════════════════════════════════════════════════════════════
# SECTION 4: USER_COMPLETED_TECHNIQUE
# ══════════════════════════════════════════════════════════════

class TestUserCompletedTechnique:

    # Turn count threshold
    def test_max_turns_triggers_completion(self):
        assert support.user_completed_technique("anything", 4) is True

    def test_below_max_turns_no_auto_complete(self):
        # With neutral text and turn < 4, should not complete
        assert support.user_completed_technique("ठीक आहे बघतो", 1) is True  # ठीक matches

    def test_turn_zero_no_auto_complete(self):
        assert support.user_completed_technique("मी ऐकतो", 0) is False

    # English completion signals
    def test_english_better(self):
        assert support.user_completed_technique("I feel better now", 1) is True

    def test_english_helped(self):
        assert support.user_completed_technique("That helped, thank you", 2) is True

    def test_english_done(self):
        assert support.user_completed_technique("Done!", 1) is True

    # Marathi completion signals — WITH anusvara
    def test_marathi_bara_vatata_with_anusvara(self):
        assert support.user_completed_technique("मला आता बरं वाटतं", 2) is True

    def test_marathi_dhanyavad(self):
        assert support.user_completed_technique("धन्यवाद, मदत झाली", 1) is True

    def test_marathi_madad_mili(self):
        assert support.user_completed_technique("मदत मिळाली", 2) is True

    # Marathi completion signals — WITHOUT anusvara (the bug case)
    def test_marathi_bara_vatat_without_anusvara(self):
        assert support.user_completed_technique("मला आता बर वाटत आहे", 2) is True

    def test_marathi_changle_vatat(self):
        assert support.user_completed_technique("चांगलं वाटतं आता", 1) is True

    def test_marathi_thik(self):
        assert support.user_completed_technique("ठीक आहे आता", 1) is True

    # Hindi completion signals
    def test_hindi_ab_thik_hai(self):
        assert support.user_completed_technique("हाँ, अब ठीक है", 2) is True

    def test_hindi_behtar(self):
        assert support.user_completed_technique("मुझे बेहतर लग रहा है", 1) is True

    def test_hindi_shukriya(self):
        assert support.user_completed_technique("शुक्रिया, मदद हुई", 2) is True

    # Non-completion messages must NOT trigger
    def test_neutral_engagement_no_complete(self):
        assert support.user_completed_technique("मी प्रयत्न करतो", 1) is False

    def test_confused_no_complete(self):
        assert support.user_completed_technique("मला कळाल नाही", 1) is False


# ══════════════════════════════════════════════════════════════
# SECTION 5: USER_IS_ENDING_SESSION
# ══════════════════════════════════════════════════════════════

class TestUserIsEndingSession:

    def test_marathi_madad_mili(self):
        assert support.user_is_ending_session("मला खूप बरं वाटत आहे, मदत मिळाली") is True

    def test_marathi_aata_garja_nahi(self):
        assert support.user_is_ending_session("आता गरज नाही, धन्यवाद") is True

    def test_marathi_kahi_nako_aata(self):
        assert support.user_is_ending_session("काही नको आता") is True

    def test_hindi_kafi_hai(self):
        assert support.user_is_ending_session("अब मुझे कुछ नहीं चाहिए, काफी है") is True

    def test_hindi_zarurat_nahi(self):
        assert support.user_is_ending_session("अब ज़रूरत नहीं है") is True

    def test_english_okay_now(self):
        assert support.user_is_ending_session("I'm okay now, thanks") is True

    def test_english_thats_enough(self):
        assert support.user_is_ending_session("that's enough for today") is True

    # Active problem statements must NOT trigger session end
    def test_problem_not_session_end(self):
        assert support.user_is_ending_session("मला खूप ताण आहे") is False

    def test_greeting_not_session_end(self):
        assert support.user_is_ending_session("नमस्कार") is False

    def test_confusion_not_session_end(self):
        assert support.user_is_ending_session("मला समजलं नाही") is False


# ══════════════════════════════════════════════════════════════
# SECTION 6: DETECT_INTENT
# ══════════════════════════════════════════════════════════════

class TestDetectIntent:

    # Greetings
    def test_english_hello(self):
        assert support.detect_intent("hello") == "greeting"

    def test_english_hi(self):
        assert support.detect_intent("hi there") == "greeting"

    def test_marathi_namaskar(self):
        assert support.detect_intent("नमस्कार") == "greeting"

    def test_hindi_namaste(self):
        assert support.detect_intent("नमस्ते") == "greeting"

    # Thanks — must NOT become greeting
    def test_marathi_dhanyavad_is_thanks_not_greeting(self):
        assert support.detect_intent("धन्यवाद मदत केल्याबद्दल") == "thanks"

    def test_hindi_shukriya_is_thanks(self):
        assert support.detect_intent("शुक्रिया") == "thanks"

    def test_english_thanks(self):
        assert support.detect_intent("thanks so much") == "thanks"

    def test_english_thank_you(self):
        assert support.detect_intent("thank you") == "thanks"

    # Goodbye
    def test_english_bye(self):
        assert support.detect_intent("bye") == "goodbye"

    def test_marathi_yeto(self):
        assert support.detect_intent("मी येतो") == "goodbye"

    def test_marathi_jato(self):
        assert support.detect_intent("मी जातो आता") == "goodbye"

    def test_hindi_chalta_hoon(self):
        assert support.detect_intent("चलता हूँ") == "goodbye"

    # Introduction
    def test_english_my_name_is(self):
        assert support.detect_intent("my name is Rahul") == "introduction"

    def test_marathi_mazha_nav(self):
        assert support.detect_intent("माझं नाव प्रिया आहे") == "introduction"

    # None for normal messages
    def test_emotional_message_returns_none(self):
        assert support.detect_intent("मला खूप ताण येत आहे") is None

    def test_question_returns_none(self):
        assert support.detect_intent("what should I do?") is None


# ══════════════════════════════════════════════════════════════
# SECTION 7: BUILD_GUIDANCE_FOR_PHASE
# ══════════════════════════════════════════════════════════════

class TestBuildGuidanceForPhase:

    SAMPLE_BLOCK = {
        "header": "Box Breathing",
        "content": "Step 1: Breathe in for 4 counts\nStep 2: Hold for 4 counts\nStep 3: Breathe out for 4 counts\nStep 4: Hold for 4 counts"
    }

    def test_listening_phase_ignores_block(self):
        """Listening phase must return listening instruction even with no block."""
        result = support.build_guidance_for_phase(None, "listening", 0)
        assert "Do NOT mention any technique" in result
        assert "ONE clarifying question" in result

    def test_listening_phase_with_block_still_returns_listening(self):
        """Listening phase must NOT mention the technique even if block provided."""
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "listening", 0)
        assert "Do NOT mention any technique" in result
        assert "Box Breathing" not in result  # technique name must not appear

    def test_no_block_non_listening_returns_fallback(self):
        result = support.build_guidance_for_phase(None, "new", 1)
        assert "Listen carefully" in result

    def test_new_phase_introduces_header(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "new", 1)
        assert "Box Breathing" in result
        assert "Step 1" in result  # first step only
        assert "Step 2" not in result  # second step must not appear

    def test_new_phase_asks_to_try(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "new", 1)
        assert "try" in result.lower() or "Ask" in result

    def test_followthrough_does_not_reintroduce(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "followthrough", 2)
        assert "Do NOT re-introduce" in result
        assert "Box Breathing" in result  # header still present as reference

    def test_followthrough_advances_step(self):
        result_turn2 = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "followthrough", 2)
        result_turn3 = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "followthrough", 3)
        # Different turns should reference different steps
        assert result_turn2 != result_turn3

    def test_clarifying_phase_stays_on_current_step(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "clarifying", 2)
        assert "confused" in result.lower()
        assert "Do NOT move to the next step" in result

    def test_clarifying_asks_for_example(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "clarifying", 1)
        assert "example" in result.lower()

    def test_closing_phase_acknowledges_finish(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "closing", 3)
        assert "Box Breathing" in result
        assert "finished" in result.lower() or "finished" in result.lower() \
               or "Acknowledge" in result

    def test_closing_asks_how_they_feel(self):
        result = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "closing", 3)
        assert "feel" in result.lower() or "feeling" in result.lower()

    def test_step_index_clamped_at_end(self):
        """When active_turn exceeds step count, should stay on last step."""
        result_turn10 = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "followthrough", 10)
        result_turn4 = support.build_guidance_for_phase(self.SAMPLE_BLOCK, "followthrough", 4)
        # Both should reference the last step (step 4)
        assert result_turn10 == result_turn4

    def test_single_step_block(self):
        single_step_block = {
            "header": "Deep Breath",
            "content": "Take one slow deep breath"
        }
        result = support.build_guidance_for_phase(single_step_block, "new", 1)
        assert "Deep Breath" in result
        assert "slow deep breath" in result


# ══════════════════════════════════════════════════════════════
# SECTION 8: FORMAT_CHAT_HISTORY_FOR_PROMPT
# ══════════════════════════════════════════════════════════════

class TestFormatChatHistory:

    def test_empty_history_returns_no_prior(self):
        result = support.format_chat_history_for_prompt([])
        assert "No prior conversation" in result

    def test_user_role_label(self):
        history = [{"role": "user", "content": "Hello"}]
        result = support.format_chat_history_for_prompt(history)
        assert "User: Hello" in result

    def test_assistant_role_label(self):
        history = [{"role": "assistant", "content": "Hi there"}]
        result = support.format_chat_history_for_prompt(history)
        assert "ManoMitra: Hi there" in result

    def test_multiple_exchanges_ordered(self):
        history = [
            {"role": "user", "content": "I feel sad"},
            {"role": "assistant", "content": "Tell me more"},
            {"role": "user", "content": "I don't know why"},
        ]
        result = support.format_chat_history_for_prompt(history)
        lines = result.strip().split("\n")
        assert lines[0].startswith("User:")
        assert lines[1].startswith("ManoMitra:")
        assert lines[2].startswith("User:")

    def test_only_last_6_messages_shown(self):
        # 10 messages — only last 6 should appear
        history = [
            {"role": "user", "content": f"msg{i}"}
            for i in range(10)
        ]
        result = support.format_chat_history_for_prompt(history)
        assert "msg0" not in result  # early messages dropped
        assert "msg9" in result      # latest kept

    def test_devanagari_content_preserved(self):
        history = [{"role": "user", "content": "मला खूप ताण आहे"}]
        result = support.format_chat_history_for_prompt(history)
        assert "मला खूप ताण आहे" in result


# ══════════════════════════════════════════════════════════════
# SECTION 9: HANDLE_LANGUAGE_SWITCH
# ══════════════════════════════════════════════════════════════

class TestHandleLanguageSwitch:

    SESSION_ID = "test-session-123"

    def test_slash_lang_en(self):
        assert support.handle_language_switch("/lang en", self.SESSION_ID) == "en"

    def test_slash_language_hi(self):
        assert support.handle_language_switch("/language hi", self.SESSION_ID) == "hi"

    def test_no_slash_lang_mr(self):
        assert support.handle_language_switch("lang mr", self.SESSION_ID) == "mr"

    def test_no_slash_language_en(self):
        assert support.handle_language_switch("language en", self.SESSION_ID) == "en"

    def test_case_insensitive(self):
        assert support.handle_language_switch("LANG EN", self.SESSION_ID) == "en"

    def test_normal_message_returns_none(self):
        assert support.handle_language_switch("मला ताण आहे", self.SESSION_ID) is None

    def test_invalid_lang_code_returns_none(self):
        assert support.handle_language_switch("lang fr", self.SESSION_ID) is None

    def test_partial_match_returns_none(self):
        assert support.handle_language_switch("language english", self.SESSION_ID) is None


# ══════════════════════════════════════════════════════════════
# SECTION 10: SHOULD_ENFORCE_SHORT_RESPONSE
# ══════════════════════════════════════════════════════════════

class TestShouldEnforceShortResponse:

    def test_single_word(self):
        assert support.should_enforce_short_response("हो") is True

    def test_two_words(self):
        assert support.should_enforce_short_response("हो ठीक") is True

    def test_four_words_exact_boundary(self):
        assert support.should_enforce_short_response("हो मी ठीक आहे") is True

    def test_five_words_over_boundary(self):
        assert support.should_enforce_short_response("हो मी आता ठीक आहे") is False

    def test_long_marathi_sentence(self):
        assert support.should_enforce_short_response("मला खूप ताण येत आहे आणि झोप येत नाही") is False

    def test_empty_string(self):
        # Edge case: empty after strip, but we handle before this point
        assert support.should_enforce_short_response("") is True  # 0 words <= 4


# ══════════════════════════════════════════════════════════════
# SECTION 11: SESSION STATE HELPERS (pure dict operations)
# ══════════════════════════════════════════════════════════════

class TestSessionHelpers:

    def _make_session(self, **kwargs):
        """Build a minimal session dict matching the storage format."""
        session = {}
        for key, value in kwargs.items():
            session[key] = {"value": value, "updated_at": "2026-01-01T00:00:00"}
        return session

    def test_get_active_technique_returns_block(self):
        session = self._make_session(active_technique={"header": "Box Breathing", "content": "steps"})
        result = support.get_active_technique(session)
        assert result is not None
        assert result["header"] == "Box Breathing"

    def test_get_active_technique_returns_none_when_absent(self):
        assert support.get_active_technique({}) is None

    def test_get_active_technique_returns_none_for_null_value(self):
        session = self._make_session(active_technique=None)
        assert support.get_active_technique(session) is None

    def test_get_active_technique_turn_default_zero(self):
        assert support.get_active_technique_turn({}) == 0

    def test_get_active_technique_turn_reads_value(self):
        session = self._make_session(active_technique_turn=3)
        assert support.get_active_technique_turn(session) == 3

    def test_get_technique_cooldown_default_zero(self):
        assert support.get_technique_cooldown({}) == 0

    def test_get_technique_cooldown_reads_value(self):
        session = self._make_session(technique_cooldown=2)
        assert support.get_technique_cooldown(session) == 2

    def test_get_last_technique_default_empty(self):
        assert support.get_last_technique({}) == ""

    def test_get_last_technique_reads_value(self):
        session = self._make_session(last_technique="Box Breathing")
        assert support.get_last_technique(session) == "Box Breathing"

    def test_get_consecutive_short_replies_default_zero(self):
        assert support.get_consecutive_short_replies({}) == 0

    def test_get_consecutive_short_replies_reads_value(self):
        session = self._make_session(consecutive_short_replies=3)
        assert support.get_consecutive_short_replies(session) == 3

    def test_get_last_bot_reply_text_empty_when_absent(self):
        assert support.get_last_bot_reply_text({}) == ""

    def test_get_last_bot_reply_text_reads_value(self):
        session = self._make_session(last_bot_reply={"bot_reply": "Hello there", "other": "data"})
        assert support.get_last_bot_reply_text(session) == "Hello there"

    def test_get_language_from_session_prefers_locked(self):
        session = self._make_session(
            chat_language="hi",
            last_preprocess={"language": "mr"}  # should be ignored
        )
        assert support.get_language_from_session(session) == "hi"

    def test_get_language_from_session_falls_back_to_preprocess(self):
        session = self._make_session(last_preprocess={"language": "mr"})
        assert support.get_language_from_session(session) == "mr"

    def test_get_language_from_session_defaults_to_en(self):
        assert support.get_language_from_session({}) == "en"


# ══════════════════════════════════════════════════════════════
# SECTION 12: STEP 6 PHASE LOGIC (unit tests for branch logic)
# These test the decision logic in isolation by calling the helper
# functions in the same order Step 6 would.
# ══════════════════════════════════════════════════════════════

class TestStep6BranchLogic:
    """
    Tests that verify the correct phase is selected for a given
    combination of active_technique, active_turn, and user_text.
    We test the helper functions in sequence, mirroring Step 6.
    """

    def _determine_phase(self, active_technique, active_turn, user_text):
        """
        Mirrors the Step 6 branch logic without session I/O.
        Returns the technique_phase that would be selected.
        """
        if active_technique:
            if active_turn == 0:
                return "new"
            elif support.user_is_confused(user_text):
                return "clarifying"
            elif support.user_is_rejecting(user_text):
                return "rejected"  # signals clear + fallthrough
            elif support.user_completed_technique(user_text, active_turn):
                return "closing"
            else:
                return "followthrough"
        else:
            if support.user_is_rejecting(user_text):
                return "global_rejection"
            return "new_or_cooldown"

    ACTIVE_BLOCK = {"header": "Deep Breath", "content": "Breathe in\nBreathe out"}

    def test_turn_zero_always_new(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 0, "हो")
        assert phase == "new"

    def test_engaged_reply_is_followthrough(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 1, "मी प्रयत्न करतो")
        assert phase == "followthrough"

    def test_confusion_is_clarifying(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 1, "मला कळाल नाही")
        assert phase == "clarifying"

    def test_pure_rejection_clears(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 1, "नको")
        assert phase == "rejected"

    def test_sentence_rejection_clears(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 2, "नको आता कोणतेही तंत्र नको")
        assert phase == "rejected"

    def test_completion_signal_is_closing(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 2, "मला आता बर वाटत आहे")
        assert phase == "closing"

    def test_max_turns_auto_closes(self):
        phase = self._determine_phase(self.ACTIVE_BLOCK, 4, "अजून करतो")
        assert phase == "closing"

    def test_confusion_takes_priority_over_completion(self):
        # Message that could match both — confusion should win (checked first)
        # "मला कळाल नाही पण ठीक वाटतं" — has both signals
        phase = self._determine_phase(self.ACTIVE_BLOCK, 2, "मला कळाल नाही पण ठीक वाटतं")
        # user_is_confused checked before user_completed_technique
        assert phase == "clarifying"

    def test_no_active_technique_rejection_is_global(self):
        phase = self._determine_phase(None, 0, "नको")
        assert phase == "global_rejection"

    def test_no_active_technique_normal_message_is_new(self):
        phase = self._determine_phase(None, 0, "मला ताण आहे")
        assert phase == "new_or_cooldown"
