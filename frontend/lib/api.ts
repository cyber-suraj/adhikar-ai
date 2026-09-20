const API = process.env.NEXT_PUBLIC_API_URL || "";

export async function getPresignedUrl(fileType: string, docType: string) {
  const res = await fetch(`${API}/presign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fileType, docType }),
  });
  if (!res.ok) throw new Error("Failed to get upload URL");
  return res.json() as Promise<{ uploadUrl: string; key: string; caseId: string }>;
}

export async function uploadToS3(uploadUrl: string, file: File) {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": file.type },
  });
  if (!res.ok) throw new Error("Upload to S3 failed");
}

export async function startAnalysis(caseId: string, s3Key: string, lang = "en", scheme?: string, applicantName?: string) {
  const payload: Record<string, string> = { caseId, s3Key, lang };
  if (scheme) payload.scheme = scheme;
  if (applicantName) payload.applicantName = applicantName;

  const res = await fetch(`${API}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Analysis failed to start");
  return res.json();
}

export async function getCaseStatus(caseId: string) {
  const res = await fetch(`${API}/status/${caseId}`);
  if (!res.ok) throw new Error("Status fetch failed");
  return res.json();
}

export async function updateCaseStatus(caseId: string, status: string, notes?: string) {
  const res = await fetch(`${API}/status/${caseId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  if (!res.ok) throw new Error("Status update failed");
  return res.json();
}