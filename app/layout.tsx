import "./globals.css";
import { AuthProvider } from "./auth-provider";

export const metadata = {
  title: "AI Personal Safety Companion",
  description: "Danger Sound Detection System",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
