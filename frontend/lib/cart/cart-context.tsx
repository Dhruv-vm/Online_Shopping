"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiClient, ApiClientError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import type { Cart, CartItem } from "@/types";

interface CartContextType {
  cart: Cart | null;
  items: CartItem[];
  itemCount: number;
  totalQuantity: number;
  subtotalPaise: number;
  isLoading: boolean;
  isMutating: boolean;
  error: string | null;
  warnings: string[];
  addItem: (listingId: string, quantity?: number) => Promise<void>;
  updateQuantity: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
  clearCart: () => Promise<void>;
  refreshCart: () => Promise<void>;
  mergeGuestCart: () => Promise<void>;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();

  const refreshCart = useCallback(async (): Promise<void> => {
    try {
      const data = await apiClient.getCart();
      setCart(data);
      setError(null);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError("Failed to load cart");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // When auth state changes (e.g. login/register), auto-merge guest cart & refresh
  useEffect(() => {
    let isMounted = true;
    const syncCart = async () => {
      if (user) {
        try {
          const mergeResult = await apiClient.mergeCart();
          if (isMounted) {
            setCart(mergeResult.cart);
            setIsLoading(false);
            return;
          }
        } catch {
          // If merge fails or no guest cart, just fetch active cart
        }
      }
      if (isMounted) {
        await refreshCart();
      }
    };
    syncCart();
    return () => {
      isMounted = false;
    };
  }, [user, refreshCart]);

  const addItem = async (listingId: string, quantity = 1): Promise<void> => {
    setIsMutating(true);
    setError(null);
    try {
      const updated = await apiClient.addToCart(listingId, quantity);
      setCart(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
        throw err;
      }
      setError("Failed to add item to cart");
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const updateQuantity = async (
    itemId: string,
    quantity: number
  ): Promise<void> => {
    setIsMutating(true);
    setError(null);
    try {
      const updated = await apiClient.updateCartItemQuantity(itemId, quantity);
      setCart(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
        throw err;
      }
      setError("Failed to update item quantity");
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const removeItem = async (itemId: string): Promise<void> => {
    setIsMutating(true);
    setError(null);
    try {
      const updated = await apiClient.removeCartItem(itemId);
      setCart(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
        throw err;
      }
      setError("Failed to remove item");
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const clearCart = async (): Promise<void> => {
    setIsMutating(true);
    setError(null);
    try {
      const updated = await apiClient.clearCart();
      setCart(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
        throw err;
      }
      setError("Failed to clear cart");
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const mergeGuestCart = async (): Promise<void> => {
    setIsMutating(true);
    setError(null);
    try {
      const result = await apiClient.mergeCart();
      setCart(result.cart);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      }
    } finally {
      setIsMutating(false);
    }
  };

  const value: CartContextType = {
    cart,
    items: cart?.items || [],
    itemCount: cart?.item_count || 0,
    totalQuantity: cart?.total_quantity || 0,
    subtotalPaise: cart?.subtotal_paise || 0,
    isLoading,
    isMutating,
    error,
    warnings: cart?.warnings || [],
    addItem,
    updateQuantity,
    removeItem,
    clearCart,
    refreshCart,
    mergeGuestCart,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextType {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used within a CartProvider");
  }
  return context;
}
