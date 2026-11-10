"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { ROLES } from "@/lib/api/schemas";
import { DEMO_ACTORS, useRole } from "@/lib/session";

const ROLE_DESCRIPTIONS = {
  coordinator: "Reviews suggested transfers and accepts, changes or rejects each one.",
  sender: "Rechecks reserved units and confirms dispatch.",
  receiver: "Confirms arrival and cool-box evidence. Receipt is not a release for transfusion.",
  safety: "Reviews held units. Only this role can clear a quarantine.",
} as const;

export default function LoginPage() {
  const { setRole } = useRole();
  const router = useRouter();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Choose a demo role">
        <p>Test accounts for judges. These are demo roles, not production sign-in.</p>
      </PageHeader>
      <div className="grid gap-4 sm:grid-cols-2">
        {ROLES.map((role) => (
          <Card key={role}>
            <CardHeader>
              <CardTitle>{DEMO_ACTORS[role].title}</CardTitle>
              <CardDescription>{ROLE_DESCRIPTIONS[role]}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full"
                onClick={() => {
                  setRole(role);
                  router.push(DEMO_ACTORS[role].home);
                }}
              >
                Continue as {DEMO_ACTORS[role].title.toLowerCase()}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
