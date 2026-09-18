"use client";
import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { getPresignedUrl, uploadToS3, startAnalysis } from "@/lib/api";

type Lang = "en" | "hi" | "mr";

const LANG_NAMES: Record<Lang, string> = { en: "English", hi: "Hindi", mr: "Marathi" };
const LANG_NATIVE: Record<Lang, string> = { en: "English", hi: "हिंदी", mr: "मराठी" };

const T: Record<Lang, Record<string, string>> = {
  en: {
    heading: "Were you rejected from a government scheme?",
    sub: "Upload your rejection letter. We find the mismatch and tell you how to fix it.",
    upload: "Take photo or upload",
    change: "Change file",
    submit: "Find My Problem",
    uploading: "Uploading...",
    analyzing: "Analyzing your document...",
    how: "How it works",
    step1: "Upload", step2: "Diagnose", step3: "Fix It",
  },
  hi: {
    heading: "क्या आपका सरकारी योजना आवेदन अस्वीकार हुआ?",
    sub: "अपना अस्वीकृति पत्र अपलोड करें। हम समस्या ढूंढकर समाधान बताएंगे।",
    upload: "फोटो लें या अपलोड करें",
    change: "फ़ाइल बदलें",
    submit: "मेरी समस्या खोजें",
    uploading: "अपलोड हो रहा है...",
    analyzing: "दस्तावेज़ विश्लेषण हो रहा है...",
    how: "यह कैसे काम करता है",
    step1: "अपलोड", step2: "निदान", step3: "सुधार",
  },
  mr: {
    heading: "तुमचा सरकारी योजनेचा अर्ज नाकारला गेला का?",
    sub: "नाकारण्याचे पत्र अपलोड करा. आम्ही समस्या शोधून उपाय सांगू.",
    upload: "फोटो घ्या किंवा अपलोड करा",
    change: "फाइल बदला",
    submit: "माझी समस्या शोधा",
    uploading: "अपलोड होत आहे...",
    analyzing: "कागदपत्र तपासत आहे...",
    how: "हे कसे काम करते",
    step1: "अपलोड", step2: "निदान", step3: "सुधारणा",
  },
};

const HOWTO: Record<Lang, string[]> = {
  en: [
    "Upload your rejection letter photo or PDF",
    "We find the exact data mismatch using AWS Textract",
    "Get a pre-filled correction form for the right office",
    "Track your case until it is resolved",
  ],
  hi: [
    "अस्वीकृति पत्र की फोटो या PDF अपलोड करें",
    "हम AWS Textract से सटीक डेटा अंतर खोजते हैं",
    "सही कार्यालय के लिए पूर्व-भरा सुधार फॉर्म प्राप्त करें",
    "अपने मामले को हल होने तक ट्रैक करें",
  ],
  mr: [
    "नाकारण्याचे पत्र अपलोड करा",
    "AWS Textract वापरून नेमका फरक शोधतो",
    "योग्य कार्यालयासाठी पूर्व-भरलेला फॉर्म मिळवा",
    "प्रकरण निराकरण होईपर्यंत ट्रॅक करा",
  ],
};

export default function Home() {
  const [lang, setLang] = useState<Lang>("en");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [status, setStatus] = useState<"idle" | "uploading" | "analyzing" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const L = T[lang];

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(f.type.startsWith("image/") ? URL.createObjectURL(f) : "pdf");
    setStatus("idle");
    setErrorMsg("");
  }

  async function handleSubmit() {
    if (!file) return;
    setStatus("uploading");
    try {
      const { uploadUrl, key, caseId } = await getPresignedUrl(file.type, "rejection_letter");
      await uploadToS3(uploadUrl, file);
      setStatus("analyzing");
      await startAnalysis(caseId, key, lang);
      router.push(`/status/${caseId}?lang=${lang}`);
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    }
  }

  const steps = [L.step1, L.step2, L.step3];
  const icons = ["📤", "🔍", "📝", "✅"];

  return (
    <div>
      {/* Language switcher */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "24px", justifyContent: "flex-end" }}>
        {(["en", "hi", "mr"] as Lang[]).map((l) => (
          <button key={l} onClick={() => setLang(l)} style={{
            padding: "6px 14px", borderRadius: "999px", fontSize: "13px", fontWeight: 600,
            border: `2px solid ${lang === l ? "#E07A00" : "#D4D4D8"}`,
            background: lang === l ? "#E07A00" : "white",
            color: lang === l ? "white" : "#52525B",
            cursor: "pointer",
          }}>{LANG_NATIVE[l]}</button>
        ))}
      </div>

      {/* Progress stepper */}
      <div style={{ display: "flex", alignItems: "center", marginBottom: "28px" }}>
        {steps.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: i < steps.length - 1 ? 1 : undefined }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%", display: "flex",
              alignItems: "center", justifyContent: "center",
              background: i === 0 ? "#E07A00" : "#E4E4E7",
              color: i === 0 ? "white" : "#A1A1AA", fontSize: 13, fontWeight: 700,
            }}>{i + 1}</div>
            <span style={{ marginLeft: 6, fontSize: 13, color: i === 0 ? "#E07A00" : "#A1A1AA", fontWeight: 600 }}>{s}</span>
            {i < steps.length - 1 && <div style={{ flex: 1, height: 2, background: "#E4E4E7", margin: "0 8px" }} />}
          </div>
        ))}
      </div>

      <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "8px", lineHeight: 1.3 }}>{L.heading}</h1>
      <p style={{ color: "#52525B", marginBottom: "28px" }}>{L.sub}</p>

      {/* Upload card */}
      <div className="card" style={{ marginBottom: "16px" }}>
        <input ref={inputRef} type="file" accept="image/*,application/pdf"
          style={{ display: "none" }} onChange={handleFile} capture="environment" />
        {!file ? (
          <button onClick={() => inputRef.current?.click()} style={{
            width: "100%", minHeight: "140px", border: "2px dashed #E07A00",
            borderRadius: "12px", background: "#FFF7ED", cursor: "pointer",
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12,
          }}>
            <span style={{ fontSize: "48px" }}>📷</span>
            <span style={{ color: "#E07A00", fontWeight: 600, fontSize: "17px" }}>{L.upload}</span>
            <span style={{ color: "#52525B", fontSize: "13px" }}>JPG, PNG, or PDF</span>
          </button>
        ) : (
          <div style={{ textAlign: "center" }}>
            {preview !== "pdf"
              ? <img src={preview} alt="preview" style={{ maxHeight: "200px", borderRadius: "8px", objectFit: "cover", marginBottom: "12px" }} />
              : <div style={{ padding: "24px", background: "#F4F4F5", borderRadius: "8px", marginBottom: "12px" }}>
                  <div style={{ fontSize: "40px" }}>📄</div>
                  <p style={{ fontWeight: 600, margin: "8px 0 0" }}>{file.name}</p>
                </div>
            }
            <button onClick={() => { setFile(null); setPreview(""); }} style={{
              background: "none", border: "none", color: "#E07A00",
              cursor: "pointer", fontSize: "14px", textDecoration: "underline",
            }}>{L.change}</button>
          </div>
        )}
      </div>

      {status === "error" && (
        <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: "8px", padding: "12px 16px", marginBottom: "16px", color: "#B91C1C" }}>
          {errorMsg}
        </div>
      )}

      <button className="btn-primary" onClick={handleSubmit}
        disabled={!file || status === "uploading" || status === "analyzing"}>
        {status === "uploading" ? L.uploading
          : status === "analyzing" ? L.analyzing
          : `${L.submit} →`}
      </button>

      {/* How it works */}
      <div style={{ marginTop: "40px" }}>
        <h2 style={{ fontSize: "17px", fontWeight: 700, marginBottom: "16px", color: "#52525B" }}>{L.how}</h2>
        {HOWTO[lang].map((item, i) => (
          <div key={i} style={{ display: "flex", gap: "12px", alignItems: "flex-start", marginBottom: "12px" }}>
            <span style={{ fontSize: "22px" }}>{icons[i]}</span>
            <p style={{ margin: 0, fontSize: "15px" }}>{item}</p>
          </div>
        ))}
      </div>
    </div>
  );
}