import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "../components/ui";
export function useAction<T>(
  action: (value: T) => Promise<unknown>,
  message: string,
  done?: () => void,
) {
  const client = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: action,
    onSuccess: async () => {
      await client.invalidateQueries();
      toast(message);
      done?.();
    },
    onError: (e: Error) => toast(e.message, true),
  });
}
