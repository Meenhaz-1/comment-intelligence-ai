"use client";

import Link, { LinkProps } from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ComponentPropsWithoutRef, MouseEvent, ReactNode } from "react";

type NavigationProgressContextValue = {
  isNavigating: boolean;
  startNavigation: () => void;
  navigate: (href: string) => void;
};

const NavigationProgressContext = createContext<NavigationProgressContextValue | null>(null);

export function NavigationProgressProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isNavigating, setIsNavigating] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  function clearNavigationTimeout() {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }

  function startNavigation() {
    clearNavigationTimeout();
    setIsNavigating(true);
    timeoutRef.current = window.setTimeout(() => {
      setIsNavigating(false);
      timeoutRef.current = null;
    }, 10000);
  }

  function navigate(href: string) {
    startNavigation();
    startTransition(() => {
      router.push(href);
    });
  }

  useEffect(() => {
    setIsNavigating(false);
    clearNavigationTimeout();
  }, [pathname]);

  useEffect(() => () => clearNavigationTimeout(), []);

  const value = useMemo(
    () => ({
      isNavigating,
      startNavigation,
      navigate,
    }),
    [isNavigating],
  );

  return (
    <NavigationProgressContext.Provider value={value}>
      <div
        aria-hidden="true"
        className={`navigation-progress ${isNavigating ? "active" : ""}`}
      />
      <div
        aria-live="polite"
        aria-atomic="true"
        className={`navigation-status ${isNavigating ? "active" : ""}`}
      >
        Loading next page...
      </div>
      {children}
    </NavigationProgressContext.Provider>
  );
}

export function useNavigationProgress() {
  const context = useContext(NavigationProgressContext);

  if (!context) {
    throw new Error("useNavigationProgress must be used within NavigationProgressProvider");
  }

  return context;
}

type AppLinkProps = LinkProps &
  Omit<ComponentPropsWithoutRef<typeof Link>, "href"> & {
    children: ReactNode;
  };

export function AppLink({ children, onClick, href, ...props }: AppLinkProps) {
  const { startNavigation } = useNavigationProgress();

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);

    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      props.target === "_blank" ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    startNavigation();
  }

  return (
    <Link href={href} onClick={handleClick} {...props}>
      {children}
    </Link>
  );
}
