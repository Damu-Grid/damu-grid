"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { DEMO_ACTORS, useRole } from "@/lib/session";

export default function Home() {
  const { role } = useRole();
  const router = useRouter();

  useEffect(() => {
    router.replace(role ? DEMO_ACTORS[role].home : "/login");
  }, [role, router]);

  return <p className="text-muted-foreground">Loading…</p>;
}
