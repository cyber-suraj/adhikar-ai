import Link from "next/link";
import type { Metadata } from "next";
import { Noto_Sans } from "next/font/google";
import "./globals.css";

const notoSans = Noto_Sans({
  subsets: ["latin", "devanagari"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-noto",
});

export const metadata: Metadata = {
  title: "Adhikar AI - Know Your Right",
  description: "Upload your rejection letter. We find the mismatch and help you fix it.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className={notoSans.variable}>
        <header style={{ background: "#E07A00", color: "white", padding: "12px 20px", display: "flex", alignItems: "center", gap: "12px" }}>
          <Link
            href="/"
            style={{
              color: "white",
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: "12px",
              cursor: "pointer",
              transition: "opacity 0.15s ease",
            }}
            className="hover:opacity-90 active:opacity-80"
          >
            <span style={{ fontSize: "22px", fontWeight: 700 }}>Adhikar AI</span>
            <span style={{ fontSize: "14px", opacity: 0.85 }}>| Know Your Right</span>
          </Link>
        </header>
        <main style={{ maxWidth: "600px", margin: "0 auto", padding: "20px 16px 40px" }}>
          {children}
        </main>
        <footer style={{ textAlign: "center", padding: "20px", color: "#52525B", fontSize: "13px" }}>
          Built for AWS First Commit - Bharat Builds Tour | Team NxtTech
        </footer>
      </body>
    </html>
  );
}