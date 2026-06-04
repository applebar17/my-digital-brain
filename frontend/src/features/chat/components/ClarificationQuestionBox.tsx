import { useMemo, useState } from "react";
import type {
  ClarificationAnswerPacket,
  ClarificationPacket,
  ClarificationQuestion
} from "../../../types/chat";

interface ClarificationQuestionBoxProps {
  packet?: ClarificationPacket | null;
  isSubmitting?: boolean;
  onSubmit: (packet: ClarificationAnswerPacket) => void;
}

export function ClarificationQuestionBox({
  packet,
  isSubmitting = false,
  onSubmit
}: ClarificationQuestionBoxProps) {
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [freeText, setFreeText] = useState<Record<string, string>>({});

  const canSubmit = useMemo(() => {
    if (!packet || !onSubmit) {
      return false;
    }
    return packet.questions.every((question) => {
      if (!question.required) {
        return true;
      }
      return (
        (selected[question.question_id]?.length ?? 0) > 0 ||
        Boolean(freeText[question.question_id]?.trim())
      );
    });
  }, [freeText, onSubmit, packet, selected]);

  if (!packet) {
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
    if (!packet || !canSubmit || isSubmitting) {
      return;
    }
    onSubmit({
      packet_id: packet.packet_id,
      process_id: packet.process_id,
      answers: packet.questions.map((question) => ({
        question_id: question.question_id,
        selected_option_ids: selected[question.question_id] ?? [],
        free_text: freeText[question.question_id]?.trim() || null
      }))
    });
  }

  return (
    <aside className="memory-clarification-box" aria-live="polite">
      <div className="memory-clarification-header">
        <strong>Clarification needed</strong>
        {packet.compact_summary ? <p>{packet.compact_summary}</p> : null}
      </div>

      {packet.questions.map((question, index) => (
        <section className="memory-clarification-question" key={question.question_id}>
          <h3>
            <span>{index + 1}.</span> {question.question}
          </h3>
          {question.options.length > 0 ? (
            <div className="memory-clarification-options">
              {question.options.map((option) => {
                const isSelected = selected[question.question_id]?.includes(option.option_id);
                return (
                  <button
                    className={`memory-clarification-option ${
                      isSelected ? "is-selected" : ""
                    } ${option.recommended ? "is-recommended" : ""}`}
                    disabled={isSubmitting}
                    key={option.option_id}
                    onClick={() => toggleOption(question, option.option_id)}
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
          {question.free_text_allowed ? (
            <textarea
              aria-label={`Free text answer for ${question.question}`}
              disabled={isSubmitting}
              onChange={(event) =>
                setFreeText((current) => ({
                  ...current,
                  [question.question_id]: event.target.value
                }))
              }
              placeholder="Or answer in your own words..."
              value={freeText[question.question_id] ?? ""}
            />
          ) : null}
        </section>
      ))}

      <div className="memory-clarification-actions">
        <button disabled={!canSubmit || isSubmitting} onClick={submitAnswers} type="button">
          {isSubmitting ? "Submitting..." : "Submit answers"}
        </button>
      </div>
    </aside>
  );
}
