import { Suspense } from "react";
import StatusClient from "./StatusClient";

export function generateStaticParams() {
  return [{ caseId: "demo" }];
}

export default function Page() {
  return (
    <Suspense fallback={<div style={{ textAlign: "center", padding: "60px 0", color: "#52525B" }}>Loading your case...</div>}>
      <StatusClient />
    </Suspense>
  );
}