import { useEffect, useMemo, useState } from "react";
import type {
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
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [freeText, setFreeText] = useState<Record<string, string>>({});
  const currentQuestion = useMemo(
    () => resolveCurrentQuestion(packet, progress),
    [packet, progress]
  );
  const currentIndex = packet && currentQuestion
    ? packet.questions.findIndex((question) => question.question_id === currentQuestion.question_id)
    : -1;

  useEffect(() => {
    setSelected({});
    setFreeText({});
  }, [packet?.packet_id, currentQuestion?.question_id]);

  const canSubmit = useMemo(() => {
    if (!packet || !currentQuestion || !onSubmit || !packet.tool_call_id) {
      return false;
    }
    if (!currentQuestion.required) {
      return true;
    }
    return (
      (selected[currentQuestion.question_id]?.length ?? 0) > 0 ||
      Boolean(freeText[currentQuestion.question_id]?.trim())
    );
  }, [currentQuestion, freeText, onSubmit, packet, selected]);

  if (!packet || !currentQuestion) {
    return null;
  }

  function toggleOption(question: ClarificationQuestion, optionId: string) {
    setSelected((current) => {
      const values = current[question.question_id] ?? [];
      if (question.selection_mode === "multiple") {
        const nextValues = values.includes(optionId)
          ? values.filter((item) => item !== optionId)
          : [...values, optionId];
        return { ...current, [question.question_id]: nextValues };
      }
      return { ...current, [question.question_id]: values.includes(optionId) ? [] : [optionId] };
    });
  }

  function submitAnswers() {
    const question = currentQuestion;
    if (!packet || !question || !canSubmit || isSubmitting) {
      return;
    }
    onSubmit({
      packet_id: packet.packet_id,
      frame_id: packet.frame_id,
      tool_call_id: packet.tool_call_id ?? "",
      answers: [
        {
          question_id: question.question_id,
          selected_option_ids: selected[question.question_id] ?? [],
          free_text: freeText[question.question_id]?.trim() || null
        }
      ]
    });
  }

  return (
    <aside className="memory-clarification-box" aria-live="polite">
      <div className="memory-clarification-header">
        <strong>Clarification needed</strong>
        {packet.compact_summary ? <p>{packet.compact_summary}</p> : null}
      </div>

      <section className="memory-clarification-question" key={currentQuestion.question_id}>
        <h3>
          <span>
            {Math.max(currentIndex + 1, 1)} / {packet.questions.length}
          </span>{" "}
          {currentQuestion.question}
        </h3>
        {currentQuestion.options.length > 0 ? (
          <div className="memory-clarification-options">
            {currentQuestion.options.map((option) => {
              const isSelected = selected[currentQuestion.question_id]?.includes(option.option_id);
              return (
                <button
                  className={`memory-clarification-option ${
                    isSelected ? "is-selected" : ""
                  } ${option.recommended ? "is-recommended" : ""}`}
                  disabled={isSubmitting}
                  key={option.option_id}
                  onClick={() => toggleOption(currentQuestion, option.option_id)}
                  type="button"
                >
                  <span>{option.label}</span>
                  {option.recommended ? <em>Recommended</em> : null}
                  {option.description ? <small>{option.description}</small> : null}
                </button>
              );
            })}
          </div>
        ) : null}
        {currentQuestion.free_text_allowed ? (
          <textarea
            aria-label={`Free text answer for ${currentQuestion.question}`}
            disabled={isSubmitting}
            onChange={(event) =>
              setFreeText((current) => ({
                ...current,
                [currentQuestion.question_id]: event.target.value
              }))
            }
            placeholder="Or answer in your own words..."
            value={freeText[currentQuestion.question_id] ?? ""}
          />
        ) : null}
      </section>

      <div className="memory-clarification-actions">
        <button disabled={!canSubmit || isSubmitting} onClick={submitAnswers} type="button">
          {isSubmitting ? "Submitting..." : "Submit answer"}
        </button>
      </div>
    </aside>
  );
}

function resolveCurrentQuestion(
  packet?: ClarificationPacket | null,
  progress?: ClarificationProgress | null
): ClarificationQuestion | null {
  if (!packet) {
    return null;
  }
  if (progress?.packet_id === packet.packet_id && progress.is_complete) {
    return null;
  }
  if (progress?.current_question_id) {
    return (
      packet.questions.find((question) => question.question_id === progress.current_question_id) ??
      null
    );
  }
  const answered = new Set(progress?.answered_question_ids ?? []);
  return (
    packet.questions.find((question) => !answered.has(question.question_id)) ??
    packet.questions[0] ??
    null
  );
}
