"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

export type ResourceState<T> = {
  data: T | null;
  error: ApiError | Error | null;
  isLoading: boolean;
};

export function useApiResource<T>(load: () => Promise<T>, dependencies: readonly unknown[]): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({
    data: null,
    error: null,
    isLoading: true,
  });

  useEffect(() => {
    let isCurrent = true;
    setState((current) => ({ ...current, error: null, isLoading: true }));

    load()
      .then((data) => {
        if (isCurrent) {
          setState({ data, error: null, isLoading: false });
        }
      })
      .catch((error: Error) => {
        if (isCurrent) {
          setState({ data: null, error, isLoading: false });
        }
      });

    return () => {
      isCurrent = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  return state;
}
