import { Alert } from "@/components/ui/Alert";

type FormStatusProps = {
  error?: string;
  success?: string;
};

export function FormStatus({ error, success }: FormStatusProps) {
  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }
  if (success) {
    return <Alert variant="success">{success}</Alert>;
  }
  return null;
}
