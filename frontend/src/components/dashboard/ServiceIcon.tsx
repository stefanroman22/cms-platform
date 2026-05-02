import {
  FileText,
  Image,
  Images,
  Mail,
  LayoutGrid,
  Video,
  Download,
  Hash,
  Box,
  type LucideProps,
} from "lucide-react";

const ICON_MAP: Record<string, React.ComponentType<LucideProps>> = {
  FileText,
  Image,
  Images,
  Mail,
  LayoutGrid,
  Video,
  Download,
  Hash,
};

interface ServiceIconProps extends LucideProps {
  name: string;
}

export function ServiceIcon({ name, ...props }: ServiceIconProps) {
  const Icon = ICON_MAP[name] ?? Box;
  return <Icon {...props} />;
}
