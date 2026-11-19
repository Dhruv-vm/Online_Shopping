"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { apiClient, ApiClientError } from "@/lib/api/client";
import type { RetailerRegisterPayload, User } from "@/types";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
    phone?: string | null;
  }) => Promise<User>;
  registerRetailer: (payload: RetailerRegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshProfile = useCallback(async (): Promise<User | null> => {
    try {
      const profile = await apiClient.getProfile();
      setUser(profile);
      return profile;
    } catch {
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProfile();
  }, [refreshProfile]);

  const login = async (email: string, password: string): Promise<User> => {
    setIsLoading(true);
    try {
      const response = await apiClient.login({ email, password });
      setUser(response.user);
      return response.user;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: {
    email: string;
    password: string;
    full_name: string;
    phone?: string | null;
  }): Promise<User> => {
    setIsLoading(true);
    try {
      const response = await apiClient.register(payload);
      setUser(response.user);
      return response.user;
    } finally {
      setIsLoading(false);
    }
  };

  const registerRetailer = async (
    payload: RetailerRegisterPayload
  ): Promise<User> => {
    setIsLoading(true);
    try {
      const response = await apiClient.registerRetailer(payload);
      setUser(response.user);
      return response.user;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async (): Promise<void> => {
    try {
      await apiClient.logout();
    } catch (err) {
      // Even if network or token error, clear local auth state
      if (err instanceof ApiClientError && err.status !== 401) {
        console.error("Logout request encountered error:", err.message);
      }
    } finally {
      setUser(null);
    }
  };

  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    registerRetailer,
    logout,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
