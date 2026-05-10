from dataclasses import dataclass, field
from enum import Enum


class ConversationState(str, Enum):
    IDLE = "IDLE"
    PLACEMENT_QUESTION = "PLACEMENT_QUESTION"
    PLACEMENT_COMPLETE = "PLACEMENT_COMPLETE"
    DAILY_SESSION_START = "DAILY_SESSION_START"
    STORY_DISPLAY = "STORY_DISPLAY"
    REVIEW_PROMPT = "REVIEW_PROMPT"
    REVIEW_ANSWER_SHOWN = "REVIEW_ANSWER_SHOWN"
    VOCAB_LESSON = "VOCAB_LESSON"
    VOCAB_QUIZ = "VOCAB_QUIZ"
    GRAMMAR_LESSON = "GRAMMAR_LESSON"
    GRAMMAR_QUIZ = "GRAMMAR_QUIZ"
    USER_ADD_VOCAB_WORD = "USER_ADD_VOCAB_WORD"
    USER_ADD_VOCAB_CONFIRM = "USER_ADD_VOCAB_CONFIRM"
    SESSION_CONFIG_TYPE = "SESSION_CONFIG_TYPE"
    SESSION_CONFIG_VOCAB_COUNT = "SESSION_CONFIG_VOCAB_COUNT"
    SESSION_CONFIG_GRAMMAR_COUNT = "SESSION_CONFIG_GRAMMAR_COUNT"


@dataclass
class SessionState:
    state: ConversationState = ConversationState.IDLE
    placement_index: int = 0
    placement_scores: dict = field(default_factory=dict)  # {cefr_band: correct_count}
    pending_review_cards: list = field(default_factory=list)
    current_card_id: int | None = None
    pending_vocab_ids: list = field(default_factory=list)
    pending_grammar_ids: list = field(default_factory=list)
    current_item_type: str | None = None
    current_item_id: int | None = None
    quiz_attempts: int = 0
    pending_add_word: str | None = None
    pending_add_enriched: dict | None = None
    word_callbacks: dict = field(default_factory=dict)  # {word: story_moment}
    # Persisted so mid-review/quiz state survives bot restart
    review_prompt: str | None = None
    review_answer: str | None = None
    quiz_correct: str | None = None
    quiz_explanation: str | None = None
    session_config_type: str | None = None
    session_config_vocab_count: int | None = None
    session_config_grammar_count: int | None = None
    session_config_command: str | None = None
    session_total_vocab: int = 0

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "placement_index": self.placement_index,
            "placement_scores": self.placement_scores,
            "pending_review_cards": self.pending_review_cards,
            "current_card_id": self.current_card_id,
            "pending_vocab_ids": self.pending_vocab_ids,
            "pending_grammar_ids": self.pending_grammar_ids,
            "current_item_type": self.current_item_type,
            "current_item_id": self.current_item_id,
            "quiz_attempts": self.quiz_attempts,
            "pending_add_word": self.pending_add_word,
            "pending_add_enriched": self.pending_add_enriched,
            "word_callbacks": self.word_callbacks,
            "review_prompt": self.review_prompt,
            "review_answer": self.review_answer,
            "quiz_correct": self.quiz_correct,
            "quiz_explanation": self.quiz_explanation,
            "session_config_type": self.session_config_type,
            "session_config_vocab_count": self.session_config_vocab_count,
            "session_config_grammar_count": self.session_config_grammar_count,
            "session_config_command": self.session_config_command,
            "session_total_vocab": self.session_total_vocab,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionState":
        s = cls()
        s.state = ConversationState(d.get("state", "IDLE"))
        s.placement_index = d.get("placement_index", 0)
        s.placement_scores = d.get("placement_scores", {})
        s.pending_review_cards = d.get("pending_review_cards", [])
        s.current_card_id = d.get("current_card_id")
        s.pending_vocab_ids = d.get("pending_vocab_ids", [])
        s.pending_grammar_ids = d.get("pending_grammar_ids", [])
        s.current_item_type = d.get("current_item_type")
        s.current_item_id = d.get("current_item_id")
        s.quiz_attempts = d.get("quiz_attempts", 0)
        s.pending_add_word = d.get("pending_add_word")
        s.pending_add_enriched = d.get("pending_add_enriched")
        s.word_callbacks = d.get("word_callbacks", {})
        s.review_prompt = d.get("review_prompt")
        s.review_answer = d.get("review_answer")
        s.quiz_correct = d.get("quiz_correct")
        s.quiz_explanation = d.get("quiz_explanation")
        s.session_config_type = d.get("session_config_type")
        s.session_config_vocab_count = d.get("session_config_vocab_count")
        s.session_config_grammar_count = d.get("session_config_grammar_count")
        s.session_config_command = d.get("session_config_command")
        s.session_total_vocab = d.get("session_total_vocab", 0)
        return s
