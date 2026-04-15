import { dashboardFieldLabelCn, dashboardInputCn } from "@/lib/styles";

interface FormFieldProps {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}

export function FormField({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  required,
}: FormFieldProps) {
  return (
    <div>
      <label className={dashboardFieldLabelCn}>
        {label}
        {required && <span className="text-red-400"> *</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={dashboardInputCn}
      />
    </div>
  );
}
