"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function HealthDot() {
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    const check = () =>
      api
        .health()
        .then(() => active && setOk(true))
        .catch(() => active && setOk(false));
    check();
    const id = setInterval(check, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const color =
    ok === null ? "bg-neutral-400" : ok ? "bg-green-500" : "bg-red-500";
  const label =
    ok === null ? "Checking..." : ok ? "Backend online" : "Backend offline";

  return (
    <span className="flex items-center gap-1.5 text-xs text-neutral-500">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
