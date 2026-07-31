import { useEffect, useMemo, useState } from "react";
import type {
  ClarificationAnswer,
  ClarificationAnswerPacket,
  ClarificationPacket,
  ClarificationProgress,
  ClarificationQuestion
} from "../../../types/chat";
import type { ClarificationUiError } from "../types";

interface ClarificationQuestionBoxProps {
  packet?: ClarificationPacket | null;
  progress?: ClarificationProgress | null;
  error?: ClarificationUiError;
  isSubmitting?: boolean;
  onRecover?: () => void;
  onSubmit: (packet: ClarificationAnswerPacket) => void;
}

export function ClarificationQuestionBox({
  packet,
  progress,
  error,
  isSubmitting = false,
  onRecover,
  onSubmit
}: ClarificationQuestionBoxProps) {
  const [answers, setAnswers] = useState<Record<string, ClarificationAnswer>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [lastSubmittedPacket, setLastSubmittedPacket] = useState<ClarificationAnswerPacket>();

  useEffect(() => {
    if (!packet) {
      setAnswers({});
      setCurrentIndex(0);
      setLastSubmittedPacket(undefined);
      return;
    }
    const saved = progress?.packet_id === packet.packet_id
      ? progress.answers_by_question_id
      : {};
    setAnswers(saved);
    const firstUnanswered = packet.questions.findIndex(
      (question) => !saved[question.question_id]
    );
    setCurrentIndex(firstUnanswered >= 0 ? firstUnanswered : 0);
    setLastSubmittedPacket(undefined);
  }, [packet?.packet_id]);

  useEffect(() => {
    if (!packet || progress?.packet_id !== packet.packet_id) {
      return;
    }
    setAnswers(progress.answers_by_question_id);
    const firstUnanswered = packet.questions.findIndex(
      (question) => !progress.answers_by_question_id[question.question_id]
    );
    if (firstUnanswered >= 0) {
      setCurrentIndex(firstUnanswered);
    }
  }, [packet, progress]);

  const question = packet?.questions[currentIndex] ?? null;
  const currentAnswer = question ? answers[question.question_id] : undefined;
  const canContinue = question ? answerIsValid(question, currentAnswer) : false;
  const isLastQuestion = packet ? currentIndex === packet.questions.length - 1 : false;
  const answeredCount = packet
    ? packet.questions.filter((item) => answers[item.question_id] && answerIsValid(item, answers[item.question_id])).length
    : 0;

  const selectedOptionIds = useMemo(
    () => new Set(currentAnswer?.selected_option_ids ?? []),
    [currentAnswer?.selected_option_ids]
  );

  if (!packet || !question) {
    return null;
  }

  const activePacket = packet;
  const activeQuestion = question;

  function updateAnswer(next: ClarificationAnswer) {
    setAnswers((current) => ({ ...current, [activeQuestion.question_id]: next }));
  }

  function toggleOption(optionId: string) {
    if (activeQuestion.response_mode === "free_text" || activeQuestion.response_mode === "text_or_audio") {
      return;
    }
    const current = currentAnswer?.selected_option_ids ?? [];
    const multiple = activeQuestion.response_mode === "multiple_choice";
    const next = multiple
      ? current.includes(optionId)
        ? current.filter((item) => item !== optionId)
        : [...current, optionId]
      : current.includes(optionId)
        ? []
        : [optionId];
    updateAnswer({
      question_id: activeQuestion.question_id,
      selected_option_ids: next,
      text: null,
      audio_media_ref: null,
      normalized_text: null
    });
  }

  function updateText(text: string) {
    updateAnswer({
      question_id: activeQuestion.question_id,
      selected_option_ids: [],
      text: text || null,
      audio_media_ref: currentAnswer?.audio_media_ref ?? null,
      normalized_text: currentAnswer?.normalized_text ?? null
    });
  }

  function submitPacket() {
    const nextPacket: ClarificationAnswerPacket = {
      packet_id: activePacket.packet_id,
      frame_id: activePacket.frame_id,
      tool_call_id: activePacket.tool_call_id ?? "",
      answers: activePacket.questions.map(
        (item) =>
          answers[item.question_id] ?? {
            question_id: item.question_id,
            selected_option_ids: [],
            text: null
          }
      )
    };
    setLastSubmittedPacket(nextPacket);
    onSubmit(nextPacket);
  }

  function continueToNext() {
    if (!canContinue || isSubmitting) {
      return;
    }
    if (!isLastQuestion) {
      setCurrentIndex((current) => current + 1);
      return;
    }
    submitPacket();
  }

  return (
    <aside className="memory-clarification-box" aria-live="polite">
      <div className="memory-clarification-header">
        <div>
          <strong>Clarification needed</strong>
          <p>{answeredCount} of {activePacket.questions.length} answered</p>
        </div>
        <span>{currentIndex + 1} / {activePacket.questions.length}</span>
      </div>

      {error ? (
        <div className="memory-clarification-error" role="alert">
          <strong>{error.retryable ? "Submission needs a retry" : "This clarification is no longer active"}</strong>
          <p>{error.message}</p>
          <small>{error.code}</small>
          <div className="memory-clarification-error-actions">
            {error.retryable && lastSubmittedPacket ? (
              <button disabled={isSubmitting} onClick={() => onSubmit(lastSubmittedPacket)} type="button">
                Retry submission
              </button>
            ) : null}
            {!error.retryable && onRecover ? (
              <button disabled={isSubmitting} onClick={onRecover} type="button">
                Reload conversation
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <section className="memory-clarification-question" key={activeQuestion.question_id}>
        <div className="memory-clarification-kind">{humanize(activeQuestion.kind)}</div>
        <h3 className="memory-clarification-question-text">{activeQuestion.question}</h3>
        {activeQuestion.options.length > 0 ? (
          <div
            aria-label="Clarification options"
            className="memory-clarification-options"
            role={activeQuestion.response_mode === "multiple_choice" ? "group" : "radiogroup"}
          >
            {activeQuestion.options.map((option) => {
              const isSelected = selectedOptionIds.has(option.option_id);
              return (
                <button
                  aria-pressed={isSelected}
                  className={`memory-clarification-option ${
                    isSelected ? "is-selected" : ""
                  } ${option.recommended ? "is-recommended" : ""}`}
                  disabled={isSubmitting}
                  key={option.option_id}
                  onClick={() => toggleOption(option.option_id)}
                  type="button"
                >
                  <span>{option.label}</span>
                  {option.recommended ? <em>Recommended</em> : null}
                  {option.summary ? <small>{option.summary}</small> : null}
                </button>
              );
            })}
          </div>
        ) : null}
        {activeQuestion.allow_custom_answer ? (
          <textarea
            aria-label={`Text answer for ${activeQuestion.question}`}
            disabled={isSubmitting}
            onChange={(event) => updateText(event.target.value)}
            placeholder={activeQuestion.response_mode === "free_text" ? "Your answer..." : "Or answer in your own words..."}
            value={currentAnswer?.text ?? ""}
          />
        ) : null}
      </section>

      <div className="memory-clarification-actions">
        <button
          disabled={currentIndex === 0 || isSubmitting}
          onClick={() => setCurrentIndex((current) => current - 1)}
          type="button"
        >
          Back
        </button>
        <button disabled={!canContinue || isSubmitting} onClick={continueToNext} type="button">
          {isSubmitting ? "Submitting..." : isLastQuestion ? "Submit answers" : "Next"}
        </button>
      </div>
    </aside>
  );
}

function answerIsValid(
  question: ClarificationQuestion,
  answer: ClarificationAnswer | undefined
): boolean {
  if (!answer) {
    return !question.required;
  }
  const hasOption = answer.selected_option_ids.length > 0;
  const hasText = Boolean(answer.text?.trim() || answer.normalized_text?.trim());
  const hasAudio = Boolean(answer.audio_media_ref?.trim());
  if (answer.selected_option_ids.length > 1 && ["single_choice", "confirmation", "choice_or_text"].includes(question.response_mode)) {
    return false;
  }
  if (["free_text", "text_or_audio"].includes(question.response_mode) && hasOption) {
    return false;
  }
  if (question.allow_custom_answer === false && (hasText || hasAudio)) {
    return false;
  }
  if (!question.required) {
    return true;
  }
  return hasOption || hasText || hasAudio;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}
