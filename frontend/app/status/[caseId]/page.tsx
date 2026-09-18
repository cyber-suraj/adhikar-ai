"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getCaseStatus, updateCaseStatus } from "@/lib/api";

type Lang = "en" | "hi" | "mr";

interface Mismatch {
  field: string;
  fieldLabel: string;
  valueA: string;
  sourceA: string;
  valueB: string;
  sourceB: string;
  similarityScore: number;
  correctionOffice: string;
  correctionProcess: string;
  estimatedTimeline: string;
}

interface CaseData {
  caseId: string;
  status: string;
  scheme: string;
  rejectionReason: string;
  mismatches: Mismatch[];
  mismatchCount: number;
  diagnosisEn: string;
  diagnosisHi: string;
  diagnosisMr: string;
  correctionForm: string;
  statusMessageEn: string;
  statusMessageHi: string;
  statusMessageMr: string;
  updatedAt: string;
  usedFallback: boolean;
}

const STATUS_ORDER = ["Uploaded","Extracted","Matched","Diagnosed","Filed","InReview","Resolved"];

const STATUS_LABELS: Record<Lang, Record<string,string>> = {
  en: { Uploaded:"Uploaded",Extracted:"Extracted",Matched:"Matched",Diagnosed:"Diagnosed",Filed:"Filed",InReview:"In Review",Resolved:"Resolved" },
  hi: { Uploaded:"अपलोड",Extracted:"पठित",Matched:"मिलान",Diagnosed:"निदान",Filed:"दाखिल",InReview:"समीक्षाधीन",Resolved:"हल" },
  mr: { Uploaded:"अपलोड",Extracted:"वाचले",Matched:"जुळले",Diagnosed:"निदान",Filed:"दाखल",InReview:"तपासणी",Resolved:"निराकरण" },
};

export default function StatusPage() {
  const { caseId } = useParams() as { caseId: string };
  const searchParams = useSearchParams();
  const langParam = (searchParams.get("lang") || "en") as Lang;
  const [lang, setLang] = useState<Lang>(langParam);
  const [data, setData] = useState<CaseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      setPolling(true);
      const d = await getCaseStatus(caseId);
      setData(d);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error fetching status");
    } finally {
      setLoading(false);
      setPolling(false);
    }
  }, [caseId]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(() => {
      fetchStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  async function handleStatusUpdate(newStatus: string) {
    await updateCaseStatus(caseId, newStatus);
    await fetchStatus();
  }

  function copyForm() {
    if (data?.correctionForm) {
      navigator.clipboard.writeText(data.correctionForm);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  const getDiagnosis = () => {
    if (!data) return "";
    if (lang === "hi") return data.diagnosisHi || data.diagnosisEn;
    if (lang === "mr") return data.diagnosisMr || data.diagnosisEn;
    return data.diagnosisEn;
  };

  const getStatusMessage = () => {
    if (!data) return "";
    const msgs: Record<Lang, string> = { en: data.statusMessageEn, hi: data.statusMessageHi, mr: data.statusMessageMr };
    return msgs[lang];
  };

  if (loading) return <div style={{textAlign:"center",padding:"60px 0",color:"#52525B"}}>Loading your case...</div>;
  if (error) return <div style={{color:"#B91C1C",padding:"20px"}}>Error: {error}</div>;
  if (!data) return <div>Case not found.</div>;

  const currentStepIndex = STATUS_ORDER.indexOf(data.status);

  return (
    <div>
      <div style={{display:"flex",gap:"8px",marginBottom:"20px",justifyContent:"flex-end"}}>
        {(["en","hi","mr"] as Lang[]).map((l) => (
          <button key={l} onClick={() => setLang(l)} style={{
            padding:"5px 12px",borderRadius:"999px",fontSize:"12px",fontWeight:600,
            border:`2px solid ${lang===l?"#E07A00":"#D4D4D8"}`,
            background:lang===l?"#E07A00":"white",
            color:lang===l?"white":"#52525B",cursor:"pointer",
          }}>
            {l==="en"?"English":l==="hi"?"हिंदी":"मराठी"}
          </button>
        ))}
      </div>

      <div className="card" style={{marginBottom:"16px"}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:"8px"}}>
          <span className={`status-pill status-${data.status}`}>{STATUS_LABELS[lang][data.status]||data.status}</span>
          <button onClick={fetchStatus} style={{background:"none",border:"none",color:"#E07A00",cursor:"pointer",fontSize:"13px"}}>
            {polling?"⟳ ":""}Refresh
          </button>
        </div>
        <p style={{margin:0,fontWeight:500}}>{getStatusMessage()}</p>
        <p style={{margin:"6px 0 0",color:"#52525B",fontSize:"13px"}}>Case ID: {caseId}</p>
      </div>

      <div style={{display:"flex",overflowX:"auto",gap:0,marginBottom:"24px",paddingBottom:"4px"}}>
        {STATUS_ORDER.map((s,i) => (
          <div key={i} style={{display:"flex",alignItems:"center",flexShrink:0}}>
            <div style={{
              width:22,height:22,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",
              background:i<=currentStepIndex?"#E07A00":"#E4E4E7",
              color:i<=currentStepIndex?"white":"#A1A1AA",fontSize:11,fontWeight:700,
            }}>{i<currentStepIndex?"✓":i+1}</div>
            <span style={{marginLeft:4,fontSize:11,color:i<=currentStepIndex?"#E07A00":"#A1A1AA",fontWeight:600,whiteSpace:"nowrap"}}>
              {STATUS_LABELS[lang][s]}
            </span>
            {i<STATUS_ORDER.length-1&&<div style={{width:16,height:2,background:i<currentStepIndex?"#E07A00":"#E4E4E7",margin:"0 4px"}}/>}
          </div>
        ))}
      </div>

      <div className="card" style={{marginBottom:"16px"}}>
        <p style={{margin:0,fontSize:"14px",color:"#52525B"}}>
          Scheme: <strong>{data.scheme}</strong> &nbsp;|&nbsp; Reason: <strong>{data.rejectionReason}</strong>
        </p>
      </div>

      {data.mismatches&&data.mismatches.length>0&&(
        <div className="card" style={{marginBottom:"16px"}}>
          <h2 style={{fontSize:"17px",fontWeight:700,marginBottom:"12px"}}>Mismatch Found</h2>
          {data.mismatches.map((m,i) => (
            <div key={i} style={{border:"1px solid #FECACA",borderRadius:"10px",padding:"12px",marginBottom:"10px",background:"#FFF7F7"}}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:"8px"}}>
                <strong style={{color:"#B91C1C"}}>{m.fieldLabel}</strong>
                <span style={{fontSize:"12px",color:"#52525B"}}>Match: {m.similarityScore}%</span>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"8px"}}>
                <div style={{background:"#F4F4F5",borderRadius:"6px",padding:"8px"}}>
                  <div style={{fontSize:"11px",color:"#52525B",marginBottom:"2px"}}>{m.sourceA}</div>
                  <div style={{fontWeight:700}}>{m.valueA}</div>
                </div>
                <div style={{background:"#FEE2E2",borderRadius:"6px",padding:"8px"}}>
                  <div style={{fontSize:"11px",color:"#52525B",marginBottom:"2px"}}>{m.sourceB}</div>
                  <div style={{fontWeight:700,color:"#B91C1C"}}>{m.valueB}</div>
                </div>
              </div>
              <div style={{marginTop:"10px",fontSize:"13px",color:"#1D4ED8"}}>
                Office: <strong>{m.correctionOffice}</strong><br/>
                Process: {m.correctionProcess}<br/>
                Timeline: {m.estimatedTimeline}
              </div>
            </div>
          ))}
        </div>
      )}

      {getDiagnosis()&&(
        <div className="card" style={{marginBottom:"16px",borderLeft:"4px solid #E07A00"}}>
          <h2 style={{fontSize:"17px",fontWeight:700,marginBottom:"10px"}}>What is wrong</h2>
          {data.usedFallback&&<p style={{fontSize:"12px",color:"#52525B",fontStyle:"italic",marginBottom:"8px"}}>Template diagnosis (AI unavailable)</p>}
          <p style={{margin:0,lineHeight:1.7,whiteSpace:"pre-wrap"}}>{getDiagnosis()}</p>
        </div>
      )}

      {data.correctionForm&&(
        <div className="card" style={{marginBottom:"20px"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"10px"}}>
            <h2 style={{fontSize:"17px",fontWeight:700,margin:0}}>Correction Form</h2>
            <button onClick={copyForm} style={{
              padding:"6px 12px",borderRadius:"6px",border:"1px solid #E07A00",
              background:copied?"#1A7F37":"white",color:copied?"white":"#E07A00",
              cursor:"pointer",fontSize:"13px",fontWeight:600,
            }}>{copied?"Copied!":"Copy Form"}</button>
          </div>
          <pre style={{
            background:"#F9F9F9",border:"1px solid #E4E4E7",borderRadius:"8px",
            padding:"12px",fontSize:"13px",overflowX:"auto",whiteSpace:"pre-wrap",
            maxHeight:"300px",overflowY:"auto",
          }}>{data.correctionForm}</pre>
        </div>
      )}

      <div style={{display:"flex",flexDirection:"column",gap:"12px"}}>
        {data.status==="Diagnosed"&&(
          <button className="btn-primary" onClick={()=>handleStatusUpdate("Filed")}>I Filed the Form</button>
        )}
        {data.status==="Filed"&&(
          <button className="btn-primary" style={{background:"#1D4ED8"}} onClick={()=>handleStatusUpdate("InReview")}>Mark as In Review</button>
        )}
        {data.status==="InReview"&&(
          <button className="btn-primary" style={{background:"#1A7F37"}} onClick={()=>handleStatusUpdate("Resolved")}>Mark as Resolved</button>
        )}
      </div>

      {!["Diagnosed","Filed","InReview","Resolved"].includes(data.status)&&(
        <p style={{textAlign:"center",color:"#52525B",fontSize:"14px",marginTop:"16px"}}>Checking for updates every 5 seconds...</p>
      )}
    </div>
  );
}