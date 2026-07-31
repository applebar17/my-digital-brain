import { useEffect, useMemo, useState } from "react";
import type {
  ClarificationAnswer,
  ClarificationAnswerPacket,
  ClarificationPacket,
  ClarificationProgress,
  ClarificationQuestion
} from "../../../types/chat";

interface ClarificationQuestionBoxProps {
  packet?: ClarificationPacket | null;
  progress?: ClarificationProgress | null;
  isSubmitting?: boolean;
  onSubmit: (packet: ClarificationAnswerPacket) => void;
}

export function ClarificationQuestionBox({
  packet,
  progress,
  isSubmitting = false,
  onSubmit
}: ClarificationQuestionBoxProps) {
  const [answers, setAnswers] = useState<Record<string, ClarificationAnswer>>({});
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (!packet) {
      setAnswers({});
      setCurrentIndex(0);
      return;
    }
    const saved = progress?.packet_id === packet.packet_id
      ? progress.answers_by_question_id
      : {};
    setAnswers(saved as Record<string, ClarificationAnswer>);
    const firstUnanswered = packet.questions.findIndex(
      (question) => !saved[question.question_id]
    );
    setCurrentIndex(firstUnanswered >= 0 ? firstUnanswered : 0);
  }, [packet?.packet_id]);

  useEffect(() => {
    if (!packet || progress?.packet_id !== packet.packet_id) {
      return;
    }
    setAnswers(progress.answers_by_question_id as Record<string, ClarificationAnswer>);
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
      text: currentAnswer?.text ?? null
    });
  }

  function updateText(text: string) {
    updateAnswer({
      question_id: activeQuestion.question_id,
      selected_option_ids: currentAnswer?.selected_option_ids ?? [],
      text: text || null
    });
  }

  function continueToNext() {
    if (!canContinue || isSubmitting) {
      return;
    }
    if (!isLastQuestion) {
      setCurrentIndex((current) => current + 1);
      return;
    }
    onSubmit({
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
    });
  }

  return (
    <aside className="memory-clarification-box" aria-live="polite">
      <div className="memory-clarification-header">
        <strong>Quick question</strong>
        <span>{currentIndex + 1} / {activePacket.questions.length}</span>
      </div>

      <section className="memory-clarification-question" key={activeQuestion.question_id}>
        <h3 className="memory-clarification-question-text">{activeQuestion.question}</h3>
        {activeQuestion.options.length > 0 ? (
          <div className="memory-clarification-options">
            {activeQuestion.options.map((option) => {
              const isSelected = selectedOptionIds.has(option.option_id);
              return (
                <button
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
            placeholder="Or answer in your own words..."
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
  const hasText = Boolean(answer.text?.trim());
  if (!question.required) {
    return true;
  }
  return hasOption || (question.allow_custom_answer && hasText);
}
