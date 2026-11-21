"use client";

/**
 * DEMO SIMULATION of a Dukaan vs Dukaan auction.
 *
 * Runs only in this browser tab: the basket, the rival stores and their bids
 * are generated locally. Nothing is sent to the server, no customer is
 * involved, and nothing here ever mixes with real auctions or real bids.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Auction } from "@/lib/api/phase3";
import { formatPrice } from "@/lib/utils";

type SimBid = { store: string; price: number; at: number };
type Sim = { endsAt: number; bids: SimBid[]; done: boolean };

const ITEMS = [
  { name: "Wheat atta 5 kg", qty: 2 },
  { name: "Toor dal 1 kg", qty: 3 },
  { name: "Sunflower oil 1 L", qty: 2 },
];
const LIST_TOTAL = 125000; // paise — "your" listed price for the demo basket
const FLOOR = 98000;
const DURATION = 60;
const RIVALS = ["Demo Store A", "Demo Store B", "Demo Store C"];
const YOU = "You";

function bestPerStore(bids: SimBid[]): SimBid[] {
  const best = new Map<string, SimBid>();
  for (const b of bids) {
    const cur = best.get(b.store);
    if (!cur || b.price < cur.price) best.set(b.store, b);
  }
  return [...best.values()].sort((x, y) => x.price - y.price || x.at - y.at);
}

export function AuctionDemoSimulation({
  activeAuctions = [],
  onSimulateBid,
}: {
  activeAuctions?: Auction[];
  onSimulateBid?: (auctionId: string) => Promise<void>;
} = {}) {
  const [sim, setSim] = useState<Sim | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [price, setPrice] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const rivalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reset = useCallback(() => {
    if (rivalTimer.current) clearTimeout(rivalTimer.current);
    rivalTimer.current = null;
    setSim(null);
    setPrice("");
    setMsg(null);
  }, []);

  const start = () => {
    reset();
    setSim({ endsAt: Date.now() + DURATION * 1000, bids: [], done: false });
  };

  // clock + completion
  useEffect(() => {
    if (!sim || sim.done) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= sim.endsAt) setSim((s) => (s ? { ...s, done: true } : s));
    }, 250);
    return () => clearInterval(id);
  }, [sim]);

  // simulated rival bids every 4–9 seconds, undercutting the best price
  useEffect(() => {
    if (!sim || sim.done) return;
    rivalTimer.current = setTimeout(() => {
      setSim((s) => {
        if (!s || s.done || Date.now() >= s.endsAt) return s;
        const ranked = bestPerStore(s.bids);
        const best = ranked[0]?.price ?? LIST_TOTAL - 3000;
        const store = RIVALS[Math.floor(Math.random() * RIVALS.length)];
        const own = ranked.find((b) => b.store === store)?.price ?? Infinity;
        const target = Math.max(FLOOR, best - (500 + Math.floor(Math.random() * 2000)));
        if (target >= own || target < FLOOR) return s;
        return { ...s, bids: [...s.bids, { store, price: Math.round(target / 100) * 100, at: Date.now() }] };
      });
    }, 4000 + Math.random() * 5000);
    return () => {
      if (rivalTimer.current) clearTimeout(rivalTimer.current);
    };
  }, [sim]);

  if (!sim) {
    return (
      <div className="rounded border border-dashed border-amber-400 bg-amber-50 p-3 text-sm">
        <p className="font-semibold text-amber-900">Demo simulation</p>
        <p className="text-xs text-amber-900">
          Practise bidding against simulated stores or simulate realistic bids onto active customer auctions.
        </p>

        {activeAuctions.length > 0 && onSimulateBid && (
          <div className="mt-2.5 rounded border border-amber-300 bg-amber-100/70 p-2.5 text-xs text-amber-950">
            <p className="font-semibold text-amber-900">Live Customer Auction Simulation</p>
            <p className="mt-0.5 text-amber-800">
              There {activeAuctions.length === 1 ? "is 1 active customer auction" : `are ${activeAuctions.length} active customer auctions`}. Click to send a realistic simulated competitor bid directly to the customer screen in real time:
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {activeAuctions.map((a) => (
                <button
                  key={a.id}
                  onClick={async () => {
                    try {
                      await onSimulateBid(a.id);
                    } catch {}
                  }}
                  className="rounded bg-amber-700 px-2.5 py-1 text-xs font-medium text-white shadow-sm hover:bg-amber-800"
                >
                  Simulate Live Bid ({a.items.map((i) => i.product_name).join(", ").slice(0, 32)}…)
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-3">
          <button onClick={start} className="rounded bg-amber-600 px-3 py-1 text-xs text-white">Start standalone demo auction</button>
        </div>
      </div>
    );
  }

  const ranked = bestPerStore(sim.bids);
  const rank = ranked.findIndex((b) => b.store === YOU) + 1;
  const mine = ranked.find((b) => b.store === YOU);
  const left = Math.max(0, Math.ceil((sim.endsAt - now) / 1000));
  const winner = sim.done ? ranked[0] : null;

  const bid = () => {
    const p = Math.round(Number(price) * 100);
    if (!Number.isFinite(p) || p <= 0) return setMsg("Enter a bid amount.");
    if (p > LIST_TOTAL) return setMsg("Bid cannot exceed your listed basket total.");
    if (mine && p >= mine.price) return setMsg("Each new bid must be lower than your previous bid.");
    setMsg(null);
    setPrice("");
    setSim((s) => (s && !s.done ? { ...s, bids: [...s.bids, { store: YOU, price: p, at: Date.now() }] } : s));
  };

  return (
    <div className="rounded border-2 border-dashed border-amber-400 bg-amber-50 p-3 text-sm" aria-label="Demo simulation auction">
      <div className="flex items-center justify-between">
        <span className="rounded bg-amber-600 px-2 py-0.5 text-xs font-semibold text-white">DEMO SIMULATION · not a real auction</span>
        <span className="font-mono text-red-600">{sim.done ? "Ended" : `00:${String(left).padStart(2, "0")}`}</span>
      </div>
      <p className="mt-2">{ITEMS.map((i) => `${i.qty}× ${i.name}`).join(", ")}</p>
      <p className="text-xs text-gray-600">
        PIN Demo area · your list total {formatPrice(LIST_TOTAL)} · current winning bid {ranked[0] ? formatPrice(ranked[0].price) : "none"} · your best {mine ? formatPrice(mine.price) : "—"}
      </p>
      <p className="mt-1 text-xs">
        {rank === 0 ? (
          <span className="text-gray-600">You have not bid yet · {ranked.length} simulated store(s) bidding</span>
        ) : rank === 1 ? (
          <span className="font-semibold text-green-700">{sim.done ? "Winning bid" : "You are winning"} · position 1 of {ranked.length}</span>
        ) : (
          <span className="font-semibold text-red-700">Outbid · position {rank} of {ranked.length}</span>
        )}
      </p>
      {!sim.done && (
        <div className="mt-2 flex gap-2 text-xs">
          <input type="number" placeholder="Bid ₹" value={price} onChange={(e) => setPrice(e.target.value)} className="w-24 rounded border px-1" aria-label="Demo bid amount" />
          <button onClick={bid} className="rounded bg-blue-600 px-3 text-white">Bid</button>
        </div>
      )}
      {msg && <p className="mt-1 text-xs text-red-700">{msg}</p>}
      {sim.bids.length > 0 && (
        <ol className="mt-2 max-h-32 overflow-auto text-xs text-gray-700">
          {[...sim.bids].reverse().slice(0, 8).map((b, i) => (
            <li key={`${b.at}-${i}`}>{b.store === YOU ? "You" : b.store} bid {formatPrice(b.price)}</li>
          ))}
        </ol>
      )}
      {winner && (
        <p className="mt-2 rounded bg-white p-2 text-xs font-semibold">
          Simulation complete: {winner.store === YOU ? "you won with" : `${winner.store} won with`} {formatPrice(winner.price)}
          {rank > 1 ? " — you were outbid." : "."}
        </p>
      )}
      <button onClick={reset} className="mt-2 rounded border px-3 py-1 text-xs">Reset simulation</button>
    </div>
  );
}
