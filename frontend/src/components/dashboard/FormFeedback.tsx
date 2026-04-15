import { CheckCircle } from "lucide-react";
import { dashboardErrorBannerCn, dashboardSuccessBannerCn } from "@/lib/styles";

interface FormFeedbackProps {
  error?: string;
  success?: string;
}

export function FormFeedback({ error, success }: FormFeedbackProps) {
  if (error) {
    return <p className={dashboardErrorBannerCn}>{error}</p>;
  }
  if (success) {
    return (
      <div className={dashboardSuccessBannerCn}>
        <CheckCircle className="h-4 w-4 shrink-0" />
        {success}
      </div>
    );
  }
  return null;
}
