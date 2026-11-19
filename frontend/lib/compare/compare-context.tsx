"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

interface CompareContextType {
  compareSlugs: string[];
  compareCount: number;
  addToCompare: (slug: string) => boolean;
  removeFromCompare: (slug: string) => void;
  toggleCompare: (slug: string) => void;
  isInCompare: (slug: string) => boolean;
  clearCompare: () => void;
}

const CompareContext = createContext<CompareContextType | undefined>(undefined);

const STORAGE_KEY = "basket_compare_slugs";
const MAX_COMPARE_ITEMS = 4;

export function CompareProvider({ children }: { children: React.ReactNode }) {
  const [compareSlugs, setCompareSlugs] = useState<string[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setCompareSlugs(parsed.slice(0, MAX_COMPARE_ITEMS));
        }
      }
    } catch {
      // Storage unavailable or corrupted
    } finally {
      setIsInitialized(true);
    }
  }, []);

  useEffect(() => {
    if (isInitialized) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(compareSlugs));
      } catch {
        // Storage quota / error
      }
    }
  }, [compareSlugs, isInitialized]);

  const addToCompare = (slug: string): boolean => {
    if (compareSlugs.includes(slug)) {
      return true;
    }
    if (compareSlugs.length >= MAX_COMPARE_ITEMS) {
      return false;
    }
    setCompareSlugs((prev) => [...prev, slug]);
    return true;
  };

  const removeFromCompare = (slug: string) => {
    setCompareSlugs((prev) => prev.filter((s) => s !== slug));
  };

  const toggleCompare = (slug: string) => {
    if (compareSlugs.includes(slug)) {
      removeFromCompare(slug);
    } else {
      addToCompare(slug);
    }
  };

  const isInCompare = (slug: string): boolean => {
    return compareSlugs.includes(slug);
  };

  const clearCompare = () => {
    setCompareSlugs([]);
  };

  return (
    <CompareContext.Provider
      value={{
        compareSlugs,
        compareCount: compareSlugs.length,
        addToCompare,
        removeFromCompare,
        toggleCompare,
        isInCompare,
        clearCompare,
      }}
    >
      {children}
    </CompareContext.Provider>
  );
}

export function useCompare() {
  const context = useContext(CompareContext);
  if (!context) {
    throw new Error("useCompare must be used within a CompareProvider");
  }
  return context;
}
