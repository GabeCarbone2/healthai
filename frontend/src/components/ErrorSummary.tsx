import { AlertCircle } from "lucide-react";
import { forwardRef } from "react";

type Props = {
  title?: string;
  message: string;
};

export const ErrorSummary = forwardRef<HTMLDivElement, Props>(
  function ErrorSummary(
    { title = "Revise as informações", message }: Props,
    ref,
  ) {
    return (
      <div
        className="error-summary"
        ref={ref}
        role="alert"
        tabIndex={-1}
        aria-labelledby="error-summary-title"
      >
        <AlertCircle size={19} aria-hidden="true" />
        <div>
          <strong id="error-summary-title">{title}</strong>
          <p>{message}</p>
        </div>
      </div>
    );
  },
);
